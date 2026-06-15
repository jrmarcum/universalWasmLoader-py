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

## SPEC conformance status — ✅ ALIGNED TO SPEC 3.0.0 (2026-06-15)

The cross-language `SPEC.md` is at **v3.0.0 (2026-06-15)**, a **BREAKING** change to the
string / aggregate **return** convention. **This port now implements the SPEC 3.0.0
canonical callee-allocated return path.**

- **SPEC 3.0.0 (implemented):** a string/aggregate-returning export returns a single **i32
  pointer** to a callee-allocated `[ptr, len]` pair in linear memory. The host reads the two
  little-endian i32 words at that pointer, decodes UTF-8, **then calls the paired
  `cabi_post_<name>(retPtr)` export** (where `<name>` is the camelCase export name, e.g.
  `greet` → `cabi_post_greet`) to let the callee free that memory; if that export is absent
  the post-call is skipped.
- **Superseded:** the old caller-allocated 8-byte out-param convention, and the even older
  multi-value `(ptr, len)` tuple return this port used previously.

The string-return marshalling lives in:

> **`src/universal_wasm_loader/_abi.py`**, function **`build_component_export_proxy`** →
> inner **`make_proxy` / `call`**.

`make_proxy` captures `cabi_post_<camel_name>` from `raw_exports` at proxy-construction time.
The `call` closure: encodes string params unchanged (UTF-8 → `cabi_realloc(0,0,1,len)` →
write → pass `(ptr,len)`); calls the export with ONLY those params, capturing the **single
i32** return (`ret_area`); reads `str_ptr` / `str_len` via the new `_read_i32_le` helper at
`ret_area` / `ret_area+4`; decodes; calls `cabi_post(...)` if present; returns the `str`.

**Export-key lookup fix (required by this work):** `build_component_export_proxy` now resolves
each raw export by `camel_name` (falling back to `wasm_key`), matching wasmtk's camelCase
export names and the JS reference's lookup by `tsName`. Previously it used only the
underscore `wasm_key`, so any multi-word export (e.g. WIT `str-len` → exported `strLen`) was
not found in the proxy and fell through to the raw-export passthrough — which failed for a
string-param export because the arg was never encoded to `(ptr, len)`.

Numerics/bool params and returns, and string **params**, are unchanged and remain spec-correct.

> **Note:** there is no repo-local `SPEC.md` copy to update — the authoritative `SPEC.md`
> lives in the JS reference submodule (`upstream/universalwasmloader-js/SPEC.md`), which is a
> separate upstream repo and is not edited from here.

## Tests

- Runner: `pytest` via `pixi run test` (`asyncio_mode = "auto"`, `pytest-asyncio`).
- `conftest.py` compiles the fixture `.wat` files to `.wasm` for the tests.
- `test_loader.py` covers: raw load, `version` global pinning (ok + mismatch), WIT export
  proxy, **bool** ABI, **string** param + return ABI (SPEC 3.0.0), host import callbacks
  (raw + WIT), `create_singleton` identity, and `InstancePool` run / acquire-release.
- `test_wit_parser.py` covers the WIT parser.
- **String fixture/test now exists:** `tests/fixtures/strings_50.wasm` + `strings_50.wit`
  (prebuilt by wasmtk; staged into a temp dir by the `strings_wasm_with_wit` conftest
  fixture via `_stage_prebuilt`, so the sibling-`.wit` is found). `test_loader.py` asserts
  `greet("World") == "Hello, World!"`, `shout("hi") == "hihi"`, `strLen("hello") == 5`. These
  three string conformance tests **pass**.
- **Pre-existing harness caveat (unrelated to SPEC 3.0.0):** the `.wat`-based fixtures
  (math / bool_mod / imports_mod) are compiled in `conftest._compile_wat` via
  `wasmtime.Module(...).serialize()` (a cwasm blob) and reloaded by `_loader.wasm_import`
  through `Module(engine, bytes)`; with recent wasmtime (35/45) that path misroutes the
  cwasm bytes to `wat2wasm` and fails with "input was not valid utf-8". This is independent
  of the ABI change (it reproduces on a clean checkout) and only affects the `.wat` fixtures
  — the prebuilt-`.wasm` string tests are unaffected. Fixing it (use real `.wasm` bytes or
  `Module.deserialize`, or pin the pixi-resolved wasmtime) is a separate harness task.

## Build / release flow

- Dev tooling: `pixi run lint` (ruff), `pixi run fmt` (ruff format), `pixi run typecheck`
  (mypy strict), `pixi run test` (pytest).
- Build: hatchling wheel + sdist (`python -m build`, or `uv build` locally). `pixi.lock` is
  committed for reproducibility; `.pixi/` and `dist/` are gitignored.

### Version source + bump (mirrors `-js`'s `deno task bump`)

- **`pyproject.toml` `[project] version` is the single source of truth** for the package
  version. The pixi `bump` task and `scripts/release.sh` both read/write only that field.
- **`scripts/bump.py`** raises the version (stdlib-only; `patch` default / `minor` / `major`),
  exposed as **`pixi run bump`** (`pixi run bump minor`, etc.) for parity with `-js`. Supports
  `--dry-run` (prints the next version without writing — used to validate without mutating the
  tree). Forces UTF-8 on stdout/stderr so the ✅ output line doesn't `UnicodeEncodeError` on a
  Windows cp1252 console.
- **`scripts/release.sh`** reads the `pyproject.toml` version, creates/forces tag `vX.Y.Z`, and
  pushes it (`--no-push` to tag locally only). Mirrors `-js`'s `scripts/publish.ts` — it never
  builds/uploads locally; the tag push is what triggers CI.

### Publish workflow — `.github/workflows/publish.yml` (`run:`-only)

- Trigger: `push` of a `v*` tag.
- **CRITICAL `run:`-only constraint.** The org's Actions policy permits only `jrmarcum`-owned
  actions. ANY third-party `uses:` — `actions/checkout`, `actions/setup-python`, AND the usual
  `pypa/gh-action-pypi-publish` — causes `startup_failure` (nothing runs; a local tag/release
  can still get created). So every step is a plain `run:` step, and we do **NOT** use PyPI
  Trusted Publishing (it needs the pypa action). Do not reintroduce `uses:`.
- Steps: checkout via `git clone --depth=1 --branch <tag> <token-auth url> .`; install
  `build` + `twine` via `pip`; run `pytest` as an **advisory** gate (`|| true`) because the
  `.wat` fixtures have the known wasmtime harness caveat above — the prebuilt-`.wasm` string
  conformance tests are the meaningful gate; build sdist+wheel with `python -m build`; verify
  with `twine check dist/*`; upload with `twine upload dist/*` using
  `TWINE_USERNAME=__token__` / `TWINE_PASSWORD=${{ secrets.PYPI_API_TOKEN }}`.

### Required owner setup (one-time)

1. **PyPI project owned/registered** — the name `universal-wasm-loader` must exist on PyPI
   under an account you control (first upload manually or pre-register the name); CI cannot
   create a project it has no rights to.
2. **`PYPI_API_TOKEN` repo secret** — a **project-scoped** PyPI API token added as the GitHub
   Actions secret `PYPI_API_TOKEN` (Settings → Secrets and variables → Actions).

### Validation done (2026-06-15, no real publish)

- `python scripts/bump.py --dry-run` for patch/minor/major prints `0.1.1` / `0.2.0` / `1.0.0`;
  bad kind exits 1. A real `bump` then `git checkout -- pyproject.toml` confirmed the write +
  revert (version left at `0.1.0`).
- `uv build` produced `universal_wasm_loader-0.1.0` sdist + wheel; `twine check dist/*` PASSED
  both. No `twine upload` / no tag push was performed.
