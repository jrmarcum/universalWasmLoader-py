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

The version lives in **`pyproject.toml`** `[project] version` — the single source of truth
(`pixi.toml` mirrors it). Three scripts key off it, each shipped in **two equivalent forms**: a
Bash `.sh` and a cross-platform Nushell `.nu` (Nushell ≥ 0.113; runs on Windows/macOS/Linux
without Git Bash). Use whichever your machine has — they have identical flags and behavior.

**Tagging/releasing and publishing are deliberately decoupled:** `release` tags + pushes +
creates the GitHub Release; `publish` is a separate, auth-gated, confirmation-guarded step that
actually uploads to PyPI (irreversible). All three support `--dry-run`.

```sh
# 1) Bump the version (commits the isolated change)
bash scripts/bump-version.sh patch     #  1.0.0 -> 1.0.1   (or minor | major | X.Y.Z)
nu   scripts/bump-version.nu patch      #  …equivalent

# 2) Tag v<version>, push branch + tag, create the GitHub Release (NO PyPI upload)
bash scripts/release.sh                 #  --no-release / --no-build / --remote / --dry-run
nu   scripts/release.nu

# 3) Publish to PyPI — separate, deliberate, irreversible
bash scripts/publish.sh                 #  prompts; --yes / --dry-run / --allow-dirty / --skip-tag-check
nu   scripts/publish.nu
```

`publish` reads the version from `pyproject.toml`, requires the matching `v<version>` tag to
exist locally **and** on the remote, refuses to run without a PyPI token, and is idempotent (if
that version is already on PyPI it reports success and uploads nothing).

### Required setup for `publish` (one-time)

1. **PyPI project owned/registered.** The name `universal-wasm-loader` must exist on PyPI under
   an account you control (do the first upload, or pre-register the name).
2. **A PyPI API token in the environment** (project-scoped is best):

   ```sh
   export TWINE_USERNAME=__token__
   export TWINE_PASSWORD=pypi-XXXXXXXX     # your token; or a [pypi] entry in ~/.pypirc
   ```

### Publishing from CI instead (optional, token-free)

`.github/workflows/publish.yml` can also build + upload, but it is **manual-only**
(`workflow_dispatch`) — it does **not** fire on a tag push, so it never double-publishes
alongside `release`. Run it from the Actions tab against the release tag.

It authenticates with **PyPI Trusted Publishing over short-lived OIDC — no long-lived PyPI token
is stored in repo secrets**, so there's nothing to leak. One-time setup: register a Trusted
Publisher on PyPI (a *pending publisher* before the project's first upload) with Owner
`jrmarcum`, Repository `universalWasmLoader-py`, Workflow `publish.yml`.

> **`run:`-only workflow.** This org's GitHub Actions policy permits only `jrmarcum`-owned
> actions; any third-party `uses:` step (including `actions/checkout` and
> `pypa/gh-action-pypi-publish`) causes a `startup_failure`. The workflow therefore uses plain
> `run:` steps throughout — including the OIDC exchange (`ACTIONS_ID_TOKEN_REQUEST_*` →
> `https://pypi.org/_/oidc/mint-token` → `twine upload` with the ephemeral token), done by hand
> rather than via the pypa publish action.
