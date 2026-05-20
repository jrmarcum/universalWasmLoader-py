# universalWasmLoader-py

Universal WASM loader for Python — a direct port of
[universalWasmLoader-js](https://github.com/jrmarcum/universalWasmLoader-js).

## Project overview

Python library that loads and instantiates WebAssembly (WASM) modules with optional
Canonical ABI support via companion WIT files.

- **License:** MIT (copyright 2026 Jon Marcum)
- **Language:** Python ≥ 3.11
- **PyPI package name:** `universal-wasm-loader`
- **Status:** Active development — targeting PyPI publication

## Upstream reference

The JavaScript implementation is the canonical reference for API design, behavior,
and conformance tests. When behavior is ambiguous, consult the JS source first.

- **Repo:** <https://github.com/jrmarcum/universalWasmLoader-js.git>
- **Local path:** `upstream/universalwasmloader-js/` (git submodule — run `git submodule update --init` after cloning)
- `universal-wasm-loader.js` — main loader (`wasmImport`, `createSingleton`, `InstancePool`)
- `wit-parser.js` — WIT companion-file parser
- `abi.js` — Canonical ABI bridge (string/bool encoding)
- `SPEC.md` — specification and seven conformance test fixtures
- `how-to-use.js` — usage examples

## Repository layout

```text
universalWasmLoader-py/
├── CLAUDE.md                    # project memory & instructions (committed)
├── LICENSE
├── README.md
├── pixi.toml                    # pixi project config & task runner
├── pyproject.toml               # Python package metadata (hatchling)
├── pixi.lock                    # lockfile — commit for reproducibility
├── .gitignore
├── src/
│   └── universal_wasm_loader/
│       ├── __init__.py          # public re-exports
│       ├── _loader.py           # wasm_import, create_singleton, InstancePool
│       ├── _wit_parser.py       # WIT companion-file parser
│       └── _abi.py              # Canonical ABI bridge
└── tests/
    ├── conftest.py              # pytest fixtures (compile WAT → WASM)
    ├── test_wit_parser.py
    ├── test_loader.py
    └── fixtures/                # WAT + WIT source files for tests
        ├── math.wat / math.wit
        ├── bool_mod.wat / bool_mod.wit
        └── imports_mod.wat / imports_mod.wit
```

## Toolchain

- **Package/env manager:** pixi (conda-forge channels + PyPI deps)
- **WASM runtime:** wasmtime ≥ 26.0.0
- **Linter:** Ruff
- **Type checker:** mypy (strict)
- **Test runner:** pytest + pytest-asyncio
- **Build backend:** hatchling

## Common tasks

```sh
pixi run test        # pytest tests/ -v
pixi run lint        # ruff check src/ tests/
pixi run fmt         # ruff format src/ tests/
pixi run typecheck   # mypy src/
```

## Public API

```python
from universal_wasm_loader import wasm_import, create_singleton, InstancePool

# Load a module (async); returns dict of callable exports
exports = await wasm_import("./math.wasm")
result = exports["calculate"](1, 2)          # 3

# Version pinning — throws if module's 'version' global ≠ 1
exports = await wasm_import("./math.wasm@1")

# Singleton — same instance returned on every call (CLI use-case)
get_math = create_singleton("./math.wasm")
math = await get_math()

# Instance pool — N independent instances for concurrent workloads
pool = InstancePool("./math.wasm", size=2)
r1, r2 = await asyncio.gather(
    pool.run(lambda m: m["calculate"](1, 1)),
    pool.run(lambda m: m["calculate"](2, 2)),
)
```

## WIT companion files

If a `.wit` file exists alongside the `.wasm` file, the loader applies Canonical ABI:

- `bool` ↔ i32 (0 / 1)
- `string` ↔ (ptr: i32, len: i32) via UTF-8 + `cabi_realloc`
- kebab-case WIT names → camelCase Python keys (e.g. `is-positive` → `isPositive`)

Without a WIT file, raw WASM exports are returned as-is with snake_case names.

## PyPI publication

Target package name: `universal-wasm-loader`. Publish once the library passes all
seven upstream conformance tests. Use `hatchling` build + twine/flit/pixi publish.

## Development notes

- `.pixi/` is gitignored (local env); `pixi.lock` should be committed
- `tempCodeRunnerFile.py` is gitignored (VS Code Code Runner artifact)
- All project context and memory lives in this CLAUDE.md — do not store
  project state in machine-local Claude memory files (keeps the repo portable)
