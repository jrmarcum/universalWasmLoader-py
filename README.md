# universalWasmLoader-py

Universal WASM loader for Python — the Python port of
[universalWasmLoader-js](https://github.com/jrmarcum/universalWasmLoader-js). Loads and
instantiates WebAssembly modules and, when a companion `.wit` file is present, applies the
Canonical ABI so you call WIT exports with idiomatic Python values (`int`/`float`, `bool`,
`str`) instead of raw i32/pointer pairs.

- **PyPI package:** `universal-wasm-loader`
- **WASM runtime:** [`wasmtime`](https://pypi.org/project/wasmtime/) ≥ 26.0.0
- **License:** MIT

## Install

```sh
pip install universal-wasm-loader
```

## Usage

```python
from universal_wasm_loader import wasm_import, create_singleton, InstancePool

exports = await wasm_import("./math.wasm")
result = exports["calculate"](1, 2)          # 3
```

See [`CLAUDE.md`](CLAUDE.md) / [`cmem/overview.md`](cmem/overview.md) for the full API surface.

## Develop

```sh
pixi run test        # pytest tests/ -v
pixi run lint        # ruff check src/ tests/
pixi run typecheck   # mypy src/
```

## Release / publish to PyPI

The version lives in **`pyproject.toml`** (the single source of truth). Publishing happens
**only in CI** — pushing a `vX.Y.Z` tag triggers `.github/workflows/publish.yml`, which builds
the sdist + wheel and uploads them to PyPI.

> **`run:`-only workflow.** This org's GitHub Actions policy permits only `jrmarcum`-owned
> actions; any third-party `uses:` step (including `actions/checkout` and
> `pypa/gh-action-pypi-publish`) causes a `startup_failure`. So the publish workflow uses plain
> `run:` steps throughout: checkout via `git clone`, install `build`/`twine` via `pip`, and
> upload via `twine` with a token (no Trusted Publishing).

### Bump → tag → push

```sh
pixi run bump            # 0.1.0 -> 0.1.1   (patch, default)
pixi run bump minor      # 0.1.0 -> 0.2.0
pixi run bump major      # 0.1.0 -> 1.0.0

git commit -am "bump version to vX.Y.Z"
bash scripts/release.sh  # reads pyproject.toml version, tags vX.Y.Z, pushes -> CI publishes
```

`python scripts/bump.py --dry-run [part]` prints the next version without writing the file.

### Required owner setup (one-time)

1. **PyPI project must exist / be owned.** The project name `universal-wasm-loader` must be
   registered on PyPI under an account you control (do the first upload manually, or register
   the name) — CI cannot create a project it has no rights to.
2. **`PYPI_API_TOKEN` GitHub repo secret.** Create a **project-scoped** PyPI API token
   (PyPI → Account settings → API tokens → scope to `universal-wasm-loader`) and add it as a
   repository secret named **`PYPI_API_TOKEN`** (Settings → Secrets and variables → Actions).
   The workflow uses it as `TWINE_USERNAME=__token__` / `TWINE_PASSWORD=${{ secrets.PYPI_API_TOKEN }}`.
