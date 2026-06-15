from __future__ import annotations

from typing import Any, Callable

import wasmtime


def _decode_string(memory: wasmtime.Memory, store: wasmtime.Store, ptr: int, length: int) -> str:
    return bytes(memory.read(store, ptr, ptr + length)).decode("utf-8")


def _read_i32_le(memory: wasmtime.Memory, store: wasmtime.Store, addr: int) -> int:
    return int.from_bytes(bytes(memory.read(store, addr, addr + 4)), "little", signed=True)


def _encode_string(
    memory: wasmtime.Memory,
    store: wasmtime.Store,
    realloc: wasmtime.Func,
    text: str,
) -> tuple[int, int]:
    data = text.encode("utf-8")
    ptr: int = realloc(store, 0, 0, 1, len(data))  # type: ignore[assignment]
    memory.write(store, data, ptr)
    return ptr, len(data)


def build_component_import_env(
    imports: list[dict],  # type: ignore[type-arg]
    callbacks: dict[str, Callable] | None,  # type: ignore[type-arg]
    memory_ref: list[wasmtime.Memory | None],
    store: wasmtime.Store,
) -> dict[str, Callable]:  # type: ignore[type-arg]
    callbacks = callbacks or {}

    def make_wrapper(fd: dict, cb: Callable | None) -> Callable:  # type: ignore[type-arg]
        has_str = any(p["type"] == "string" for p in fd["params"])

        def wrapper(*raw_args: Any) -> Any:
            memory = memory_ref[0]
            converted: list[Any] = []
            idx = 0
            for p in fd["params"]:
                val = raw_args[idx]
                idx += 1
                if p["type"] == "bool":
                    converted.append(bool(val))
                elif p["type"] == "string" and has_str and memory is not None:
                    length = int(raw_args[idx])
                    idx += 1
                    converted.append(_decode_string(memory, store, int(val), length))
                else:
                    converted.append(val)
            if cb is None:
                return None if not fd["return_type"] else 0
            result = cb(*converted)
            if result is None:
                return 0
            return int(result) if isinstance(result, bool) else result

        return wrapper

    env: dict[str, Callable] = {}  # type: ignore[type-arg]
    for func_def in imports:
        cb = callbacks.get(func_def["camel_name"]) or callbacks.get(func_def["name"])
        env[func_def["wasm_key"]] = make_wrapper(func_def, cb)
    return env


def build_component_export_proxy(
    raw_exports: dict[str, Any],
    wit_exports: list[dict],  # type: ignore[type-arg]
    memory_ref: list[wasmtime.Memory | None],
    store: wasmtime.Store,
    cabi_realloc_ref: list[wasmtime.Func | None],
) -> dict[str, Callable]:  # type: ignore[type-arg]
    def make_proxy(fd: dict, raw_fn: wasmtime.Func) -> Callable:  # type: ignore[type-arg]
        # SPEC 3.0.0: a string/aggregate-returning export returns a single i32
        # pointer to a callee-allocated [ptr, len] pair. After reading it, the
        # host calls the paired cabi_post_<name>(retArea) export (if present) to
        # let the callee free that memory. <name> is the camelCase export name.
        cabi_post = raw_exports.get(f"cabi_post_{fd['camel_name']}")
        if not isinstance(cabi_post, wasmtime.Func):
            cabi_post = None

        def call(*args: Any) -> Any:
            memory = memory_ref[0]
            realloc = cabi_realloc_ref[0]
            wasm_args: list[Any] = []
            for p, val in zip(fd["params"], args):
                if p["type"] == "bool":
                    wasm_args.append(int(bool(val)))
                elif p["type"] == "string" and memory is not None and realloc is not None:
                    ptr, length = _encode_string(memory, store, realloc, str(val))
                    wasm_args.extend([ptr, length])
                else:
                    wasm_args.append(val)
            result = raw_fn(store, *wasm_args)
            rt = fd.get("return_type")
            if rt == "bool":
                return bool(result)
            if rt == "string" and memory is not None:
                # The export returns a single i32 pointing at the 8-byte
                # [ptr, len] return area (callee-allocated).
                ret_area = int(result)
                str_ptr = _read_i32_le(memory, store, ret_area)
                str_len = _read_i32_le(memory, store, ret_area + 4)
                decoded = _decode_string(memory, store, str_ptr, str_len)
                if cabi_post is not None:
                    cabi_post(store, ret_area)
                return decoded
            return result

        return call

    proxy: dict[str, Callable] = {}  # type: ignore[type-arg]
    for func_def in wit_exports:
        # wasmtk emits camelCase export names (e.g. WIT `str-len` -> `strLen`),
        # matching the reference loader's lookup by camelCase tsName. Fall back
        # to the underscore form for tolerance.
        raw_fn = raw_exports.get(func_def["camel_name"]) or raw_exports.get(func_def["wasm_key"])
        if raw_fn is not None and isinstance(raw_fn, wasmtime.Func):
            proxy[func_def["camel_name"]] = make_proxy(func_def, raw_fn)
    return proxy
