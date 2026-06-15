from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from universal_wasm_loader import InstancePool, create_singleton, wasm_import


# ── raw load (no WIT) ─────────────────────────────────────────────────────────

async def test_raw_load_calculate(math_wasm_path: Path) -> None:
    exports = await wasm_import(math_wasm_path)
    assert callable(exports["calculate"])
    assert exports["calculate"](1, 2) == 3
    assert exports["calculate"](10, -3) == 7


async def test_raw_load_version_global(math_wasm_path: Path) -> None:
    exports = await wasm_import(math_wasm_path)
    assert exports["version"] == 1


# ── version pinning ───────────────────────────────────────────────────────────

async def test_version_pinning_ok(math_wasm_path: Path) -> None:
    exports = await wasm_import(f"{math_wasm_path}@1")
    assert exports["calculate"](3, 4) == 7


async def test_version_pinning_mismatch(math_wasm_path: Path) -> None:
    with pytest.raises(RuntimeError, match="version mismatch"):
        await wasm_import(f"{math_wasm_path}@2")


# ── WIT export proxy ─────────────────────────────────────────────────────────

async def test_wit_export_proxy(math_wasm_with_wit: Path) -> None:
    exports = await wasm_import(math_wasm_with_wit)
    assert callable(exports["calculate"])
    assert exports["calculate"](10, 5) == 15


# ── bool ABI ─────────────────────────────────────────────────────────────────

async def test_bool_export(bool_wasm_with_wit: Path) -> None:
    exports = await wasm_import(bool_wasm_with_wit)
    assert exports["isPositive"](5) is True
    assert exports["isPositive"](-1) is False
    assert exports["isPositive"](0) is False


async def test_bool_is_even(bool_wasm_with_wit: Path) -> None:
    exports = await wasm_import(bool_wasm_with_wit)
    assert exports["isEven"](4) is True
    assert exports["isEven"](3) is False


# ── string ABI (SPEC 3.0.0: callee-allocated return + cabi_post) ──────────────

async def test_string_greet(strings_wasm_with_wit: Path) -> None:
    exports = await wasm_import(strings_wasm_with_wit)
    assert exports["greet"]("World") == "Hello, World!"


async def test_string_shout(strings_wasm_with_wit: Path) -> None:
    exports = await wasm_import(strings_wasm_with_wit)
    assert exports["shout"]("hi") == "hihi"


async def test_string_len(strings_wasm_with_wit: Path) -> None:
    exports = await wasm_import(strings_wasm_with_wit)
    assert exports["strLen"]("hello") == 5


# ── host import callbacks ─────────────────────────────────────────────────────

async def test_host_callbacks_raw(imports_wasm_path: Path) -> None:
    callbacks = {
        "env_mul": lambda a, b: a * b,
        "env_add": lambda a, b: a + b,
    }
    exports = await wasm_import(imports_wasm_path, callbacks)
    assert exports["scale"](3.0, 4.0) == pytest.approx(12.0)
    assert exports["combine"](10, 7) == 17


async def test_host_callbacks_wit(imports_wasm_with_wit: Path) -> None:
    callbacks = {
        "envMul": lambda a, b: a * b,
        "envAdd": lambda a, b: a + b,
    }
    exports = await wasm_import(imports_wasm_with_wit, callbacks)
    assert exports["scale"](3.0, 4.0) == pytest.approx(12.0)
    assert exports["combine"](10, 7) == 17


# ── create_singleton ──────────────────────────────────────────────────────────

async def test_create_singleton_same_instance(math_wasm_path: Path) -> None:
    get_math = create_singleton(math_wasm_path)
    a = await get_math()
    b = await get_math()
    assert a is b


async def test_create_singleton_works(math_wasm_path: Path) -> None:
    get_math = create_singleton(math_wasm_path)
    math = await get_math()
    assert math["calculate"](2, 3) == 5


# ── InstancePool ──────────────────────────────────────────────────────────────

async def test_instance_pool_run(math_wasm_path: Path) -> None:
    pool = InstancePool(math_wasm_path, size=2)
    r1, r2 = await asyncio.gather(
        pool.run(lambda m: m["calculate"](1, 1)),
        pool.run(lambda m: m["calculate"](2, 2)),
    )
    assert r1 == 2
    assert r2 == 4


async def test_instance_pool_acquire_release(math_wasm_path: Path) -> None:
    pool = InstancePool(math_wasm_path, size=1)
    inst = await pool.acquire()
    assert inst["calculate"](5, 5) == 10
    await pool.release(inst)
    inst2 = await pool.acquire()
    assert inst2 is inst
