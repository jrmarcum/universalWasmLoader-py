> **⚠️ PORTABLE PROJECT MEMORY LIVES IN `cmem/`** — start at [`cmem/INDEX.md`](cmem/INDEX.md).
> When saving new project memory, write it into the matching `cmem/` topic file (and refresh its
> pointer in `cmem/INDEX.md`). The **"update the project memory"** and **"look for code issues"**
> triggers are defined in `cmem/INDEX.md` and are binding on every agent.

# universalWasmLoader-py

Python port of the [Universal WASM Loader](https://github.com/jrmarcum/universalWasmLoader-js).
Loads and instantiates WebAssembly modules and, when a companion `.wit` file is present, applies
the Canonical ABI so you call WIT exports with idiomatic Python values (`int`/`float`, `bool`,
`str`). Built on [`wasmtime`](https://pypi.org/project/wasmtime/) (wasmtime-py). See
[`README.md`](README.md) for user-facing docs and [`cmem/overview.md`](cmem/overview.md) for the
project memory.

## Quick orientation

- `src/universal_wasm_loader/_loader.py` — core: `wasm_import`, `create_singleton`, `InstancePool`,
  version pinning (`@N` suffix vs. an exported `version` global).
- `src/universal_wasm_loader/_abi.py` — Canonical ABI bridge (bool ↔ i32, string ↔ `(ptr,len)`,
  SPEC 3.0.0 callee-allocated string returns + `cabi_post_*`).
- `src/universal_wasm_loader/_wit_parser.py` — regex WIT companion-file parser.
- `tests/` — pytest suite + `.wat`/`.wit` fixtures (`pixi run test`).
- `pyproject.toml` `[project] version` — the single source of truth for the package version.
- `scripts/bump-version.{sh,nu}` · `release.{sh,nu}` · `publish.{sh,nu}` — the release toolchain
  (paired Bash + Nushell forms). Bump → release (tag + push + GitHub Release) → publish (PyPI),
  publishing kept a deliberate, decoupled step. See [`cmem/overview.md`](cmem/overview.md).
