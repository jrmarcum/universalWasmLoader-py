# Overview — universalWasmLoader-py

## What this is

The **Python port** of the Universal WASM Loader. It loads and instantiates WebAssembly
modules and, when a companion `.wit` file is present, applies the Canonical ABI so the host
calls WIT exports with idiomatic Python values (numbers, `bool`, `str`) instead of raw i32/ptr
pairs. It is a direct port of the reference JavaScript implementation
(`universalWasmLoader-js`), which is the canonical source for API design, behavior, and
conformance tests. The JS repo is vendored as a git submodule at
`upstream/universalwasmloader-js/`.

- **License:** MIT (© 2026 Jon Marcum)
- **Status:** Active development, alpha (`Development Status :: 3 - Alpha`), targeting PyPI.

## Language / runtime

- **Language:** Python ≥ 3.11 (classifiers list 3.11 / 3.12 / 3.13).
- **WASM runtime:** [`wasmtime`](https://pypi.org/project/wasmtime/) (wasmtime-py) `>=26.0.0`,
  the only runtime dependency. The loader uses wasmtime's core API — `Engine`, `Module`,
  `Store`, `Linker`, `Instance`, `Memory`, `Func`, `Global` — NOT the higher-level Component
  Model API. Canonical ABI marshalling is implemented by hand in `_abi.py`.
- **Package/env manager:** pixi (conda-forge channel for Python; PyPI for deps). Editable
  install of the package itself plus a `dev` feature for the test/lint/type tools.
- **Build backend:** hatchling (wheel packages `src/universal_wasm_loader`).
- **Registry:** PyPI, package name **`universal-wasm-loader`** (current version `0.1.0`).

## Repository layout

```text
src/universal_wasm_loader/
  __init__.py      # public re-exports: wasm_import, create_singleton, InstancePool
  _loader.py       # core: wasm_import(), create_singleton(), InstancePool, version pinning
  _wit_parser.py   # regex WIT companion-file parser (parse_wit)
  _abi.py          # Canonical ABI bridge (import env + export proxy, string/bool marshalling)
tests/
  conftest.py      # pytest fixtures: compile fixture .wat -> .wasm for tests
  test_loader.py   # loader + ABI integration tests
  test_wit_parser.py
  fixtures/        # math.{wat,wit}, bool_mod.{wat,wit}, imports_mod.{wat,wit}
upstream/universalwasmloader-js/   # git submodule (reference impl + SPEC.md)
```

## Public API surface (what actually exists)

Idiomatic Python equivalents of the reference loader's `wasmImport` / `createSingleton` /
`InstancePool`. All three are re-exported from the package root (`__init__.py`).

- **`async wasm_import(wasm_path, host_callbacks=None) -> dict[str, Any]`** (`_loader.py`)
  — the entry point. Reads the `.wasm` bytes (off-thread via `asyncio.to_thread`), looks for a
  sibling `.wit`, instantiates via a `Linker`, and returns a dict of exports.
  - `wasm_path` is `str | Path`; a trailing `@N` suffix pins a version
    (`_parse_version_suffix`), validated against an exported `version` **global**
    (`_assert_version`, raises `RuntimeError` on mismatch / missing).
  - With a WIT file: returns the camelCase-keyed **export proxy** with ABI translation
    applied (`build_component_export_proxy`); raw exports not described by WIT are passed
    through.
  - Without a WIT file: returns raw exports wrapped for direct calling
    (`_wrap_for_user` — `Func` → callable, `Global` → its value).
  - `host_callbacks` is a flat dict of host functions the module imports; WIT imports are
    wrapped with ABI adaptation (`build_component_import_env`), and any unbound import is
    satisfied with a typed no-op stub (`_make_noop`).
- **`create_singleton(wasm_path, host_callbacks=None) -> Callable[[], Awaitable[dict]]`**
  — returns an async getter that instantiates once and returns the same instance on every
  call (CLI / DLL pattern). Guarded by an `asyncio.Lock`.
- **`class InstancePool(wasm_path, host_callbacks=None, size=2)`** — N independent instances
  in an `asyncio.Queue`; `await acquire()` / `await release(inst)` / `await run(fn)`
  (acquire → call → release, awaits coroutine results). Server / concurrent-workload pattern.

## Canonical ABI (as implemented in `_abi.py`)

- **numbers** (`s32`/`s64`/`f32`/`f64`) — passed straight through.
- **bool** ↔ i32: params `int(bool(v))`; returns `bool(result != 0)`.
- **string** ↔ `(ptr: i32, len: i32)`:
  - **params** — UTF-8 encode, allocate via the module's exported `cabi_realloc(0, 0, 1, len)`,
    write bytes into exported `memory`, pass `(ptr, len)` as two args (`_encode_string`).
  - **returns** — see conformance note below.
- **naming** — kebab-case WIT names → camelCase keys for the proxy; underscore form
  (`kebab_to_wasm_key`) for wasmtime export/import lookup. Imports resolve callbacks by
  camelCase first, then raw name.

The WIT parser (`_wit_parser.py`) is regex-based: extracts `package`, `world`, and the
`import` / `export` `func(...)` signatures; unknown param/return types collapse to `s32`.

## SPEC conformance status — ⚠️ NEEDS ALIGNMENT TO SPEC 3.0.0

The cross-language `SPEC.md` is now at **v3.0.0 (2026-06-15)**, a **BREAKING** change to the
string / aggregate **return** convention:

- **NEW (SPEC 3.0.0, canonical callee-allocated):** a string/aggregate-returning export
  returns a single **i32 pointer** to a callee-allocated `[ptr, len]` pair in linear memory.
  The host reads the two i32 words at that pointer, decodes, **then calls the paired
  `cabi_post_<name>(retPtr)` export** to let the callee free that memory.
- **OLD (caller-allocated out-param):** the host allocates an 8-byte return area and passes
  its address as a trailing arg; the callee writes `(ptr, len)` at offsets 0 / 4; no
  `cabi_post`.

**This port currently implements NEITHER cleanly — it uses an even older multi-value-return
shape and must be migrated to SPEC 3.0.0.** The string-return marshalling lives in:

> **`src/universal_wasm_loader/_abi.py`**, function **`build_component_export_proxy`** →
> inner **`make_proxy` / `call`**, **lines ~86–93**.

There, `result = raw_fn(store, *wasm_args)` and the `rt == "string"` branch reads
`result[0]` / `result[1]` from a **multi-value `(ptr, len)` tuple returned directly by the
export** (`isinstance(result, (list, tuple)) and len(result) >= 2`). There is:

- **no caller-allocated 8-byte out-param** (so it is not even the old out-param convention),
- **no callee-allocated single-pointer return** (SPEC 3.0.0), and
- **no `cabi_post_<name>` call anywhere** in the codebase (verified: `cabi_post` appears
  nowhere in `src/`).

Because this port predates 2026-06-15, a future session must rework that `call` function to
the SPEC 3.0.0 callee-allocated + `cabi_post` flow, and (likely) capture each export's
`cabi_post_<name>` from the raw exports during proxy construction. String **params** already
use `cabi_realloc` and are closer to spec, but should be re-verified against 3.0.0.

## Tests

- Runner: `pytest` via `pixi run test` (`asyncio_mode = "auto"`, `pytest-asyncio`).
- `conftest.py` compiles the fixture `.wat` files to `.wasm` for the tests.
- `test_loader.py` covers: raw load, `version` global pinning (ok + mismatch), WIT export
  proxy, **bool** ABI, host import callbacks (raw + WIT), `create_singleton` identity, and
  `InstancePool` run / acquire-release.
- `test_wit_parser.py` covers the WIT parser.
- **Gap:** there is **no string-param or string-return fixture/test** (no string `.wat`/`.wit`
  in `tests/fixtures/`), so the string-return path described above is **untested** — another
  reason to address it when aligning to SPEC 3.0.0.

## Build / release flow

- Dev tooling: `pixi run lint` (ruff), `pixi run fmt` (ruff format), `pixi run typecheck`
  (mypy strict), `pixi run test` (pytest).
- Build: hatchling wheel; publish to PyPI as `universal-wasm-loader` once the loader passes
  the upstream conformance fixtures. `pixi.lock` is committed for reproducibility; `.pixi/`
  is gitignored.
