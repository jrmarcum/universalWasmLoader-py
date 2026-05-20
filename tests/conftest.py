from __future__ import annotations

from pathlib import Path

import pytest
import wasmtime

FIXTURES = Path(__file__).parent / "fixtures"


def _compile_wat(name: str, tmp_dir: Path) -> Path:
    wat_text = (FIXTURES / f"{name}.wat").read_text(encoding="utf-8")
    engine = wasmtime.Engine()
    # Module() accepts WAT text directly; serialize() gives canonical binary
    module = wasmtime.Module(engine, wat_text)
    wasm_bytes = module.serialize()
    wasm_path = tmp_dir / f"{name}.wasm"
    wasm_path.write_bytes(wasm_bytes)
    return wasm_path


def _add_wit(name: str, wasm_path: Path) -> Path:
    wit_text = (FIXTURES / f"{name}.wit").read_text(encoding="utf-8")
    (wasm_path.parent / f"{name}.wit").write_text(wit_text, encoding="utf-8")
    return wasm_path


# ── math fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def math_wasm_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _compile_wat("math", tmp_path_factory.mktemp("math_no_wit"))


@pytest.fixture(scope="session")
def math_wasm_with_wit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    wasm = _compile_wat("math", tmp_path_factory.mktemp("math_with_wit"))
    return _add_wit("math", wasm)


# ── bool fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def bool_wasm_with_wit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    wasm = _compile_wat("bool_mod", tmp_path_factory.mktemp("bool_with_wit"))
    return _add_wit("bool_mod", wasm)


# ── imports fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def imports_wasm_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _compile_wat("imports_mod", tmp_path_factory.mktemp("imports_no_wit"))


@pytest.fixture(scope="session")
def imports_wasm_with_wit(tmp_path_factory: pytest.TempPathFactory) -> Path:
    wasm = _compile_wat("imports_mod", tmp_path_factory.mktemp("imports_with_wit"))
    return _add_wit("imports_mod", wasm)
