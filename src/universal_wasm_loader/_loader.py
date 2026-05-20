from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any, Callable

import wasmtime
from wasmtime import Engine, FuncType, Linker, Module, Store

from ._abi import build_component_export_proxy, build_component_import_env
from ._wit_parser import parse_wit


def _parse_version_suffix(path: str) -> tuple[str, int | None]:
    m = re.search(r"@(\d+)$", path)
    return (path[: m.start()], int(m.group(1))) if m else (path, None)


def _collect_raw_exports(
    module: Module, instance: wasmtime.Instance, store: Store
) -> dict[str, Any]:
    exports_obj = instance.exports(store)
    result: dict[str, Any] = {}
    for exp in module.exports:
        val = exports_obj[exp.name]
        if val is not None:
            result[exp.name] = val
    return result


def _make_noop(n_results: int) -> Callable[..., Any]:
    if n_results == 0:
        return lambda *_: None
    if n_results == 1:
        return lambda *_: 0
    return lambda *_, n=n_results: [0] * n


def _assert_version(raw: dict[str, Any], store: Store, expected: int, path: str) -> None:
    g = raw.get("version")
    if not isinstance(g, wasmtime.Global):
        raise RuntimeError(f"{path!r}: no exported 'version' global")
    actual = g.value(store)
    if actual != expected:
        raise RuntimeError(f"{path!r}: version mismatch — expected {expected}, got {actual}")


def _wrap_for_user(raw: dict[str, Any], store: Store) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, val in raw.items():
        if isinstance(val, wasmtime.Func):
            fn = val
            result[name] = lambda *args, f=fn: f(store, *args)
        elif isinstance(val, wasmtime.Global):
            result[name] = val.value(store)
        else:
            result[name] = val
    return result


async def wasm_import(
    wasm_path: str | Path,
    host_callbacks: dict[str, Callable[..., Any]] | None = None,
) -> dict[str, Any]:
    path_str = str(wasm_path)
    cleaned, requested_version = _parse_version_suffix(path_str)
    path = Path(cleaned)

    wit: dict[str, Any] | None = None
    wit_path = path.with_suffix(".wit")
    if wit_path.exists():
        try:
            wit = parse_wit(wit_path.read_text(encoding="utf-8"))
        except Exception:
            wit = None

    wasm_bytes = await asyncio.to_thread(path.read_bytes)
    engine = Engine()
    module = Module(engine, wasm_bytes)
    store = Store(engine)

    memory_ref: list[wasmtime.Memory | None] = [None]
    cabi_realloc_ref: list[wasmtime.Func | None] = [None]

    import_env: dict[str, Callable[..., Any]] = {}
    if wit:
        import_env = build_component_import_env(wit["imports"], host_callbacks, memory_ref, store)

    linker = Linker(engine)
    for imp in module.imports:
        if not isinstance(imp.type, FuncType):
            continue
        ft: FuncType = imp.type
        imp_name = imp.name
        if imp_name in import_env:
            linker.define_func(imp.module, imp_name, ft, import_env[imp_name])
        elif host_callbacks and imp_name in host_callbacks:
            cb = host_callbacks[imp_name]
            linker.define_func(imp.module, imp_name, ft, lambda *a, fn=cb: fn(*a))
        else:
            linker.define_func(imp.module, imp_name, ft, _make_noop(len(ft.results)))

    instance = linker.instantiate(store, module)
    raw = _collect_raw_exports(module, instance, store)

    mem = raw.get("memory")
    if isinstance(mem, wasmtime.Memory):
        memory_ref[0] = mem
    realloc = raw.get("cabi_realloc")
    if isinstance(realloc, wasmtime.Func):
        cabi_realloc_ref[0] = realloc

    if requested_version is not None:
        _assert_version(raw, store, requested_version, cleaned)

    if wit:
        proxy = build_component_export_proxy(
            raw, wit["exports"], memory_ref, store, cabi_realloc_ref
        )
        for name, val in raw.items():
            if name not in proxy:
                if isinstance(val, wasmtime.Func):
                    fn = val
                    proxy[name] = lambda *args, f=fn: f(store, *args)
                elif isinstance(val, wasmtime.Global):
                    proxy[name] = val.value(store)
        return proxy

    return _wrap_for_user(raw, store)


def create_singleton(
    wasm_path: str | Path,
    host_callbacks: dict[str, Callable[..., Any]] | None = None,
) -> Callable[[], Any]:
    _cache: dict[str, Any] | None = None
    _lock: asyncio.Lock | None = None

    async def get() -> dict[str, Any]:
        nonlocal _cache, _lock
        if _lock is None:
            _lock = asyncio.Lock()
        async with _lock:
            if _cache is None:
                _cache = await wasm_import(wasm_path, host_callbacks)
        return _cache

    return get


class InstancePool:
    def __init__(
        self,
        wasm_path: str | Path,
        host_callbacks: dict[str, Callable[..., Any]] | None = None,
        size: int = 2,
    ) -> None:
        self._path = wasm_path
        self._callbacks = host_callbacks
        self._size = size
        self._pool: asyncio.Queue[dict[str, Any]] | None = None
        self._lock: asyncio.Lock | None = None

    async def _ensure_ready(self) -> None:
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            if self._pool is not None:
                return
            q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
            for inst in await asyncio.gather(
                *[wasm_import(self._path, self._callbacks) for _ in range(self._size)]
            ):
                q.put_nowait(inst)
            self._pool = q

    async def acquire(self) -> dict[str, Any]:
        await self._ensure_ready()
        assert self._pool is not None
        return await self._pool.get()

    async def release(self, instance: dict[str, Any]) -> None:
        if self._pool is not None:
            await self._pool.put(instance)

    async def run(self, fn: Callable[[dict[str, Any]], Any]) -> Any:
        instance = await self.acquire()
        try:
            result = fn(instance)
            if asyncio.iscoroutine(result):
                return await result
            return result
        finally:
            await self.release(instance)
