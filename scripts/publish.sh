#!/usr/bin/env bash
# Publish this package to PyPI — a SEPARATE, deliberate step, intentionally kept
# out of release.sh (PyPI uploads are irreversible: a version can never be
# re-uploaded).
#
# Reads the version from pyproject.toml, requires the matching v<version> tag to
# already exist locally AND on the remote (so you publish exactly what was
# released), runs a fresh `python -m build`, and uploads with `twine`.
#
# Prereq order:  scripts/bump-version.sh -> scripts/release.sh -> scripts/publish.sh
#
# Usage: scripts/publish.sh [options]
#   --yes             Don't prompt for confirmation before uploading.
#   --dry-run         Print the build + upload commands; run nothing.
#   --allow-dirty     Skip the clean-working-tree check.
#   --skip-tag-check  Don't require the v<version> tag locally + on remote.
#   --remote <name>   Git remote to check the tag against (default: origin).
#   -h, --help        Show this help.
#
# Auth-gated: needs a PyPI API token in the environment —
#   export TWINE_USERNAME=__token__
#   export TWINE_PASSWORD=pypi-XXXXXXXX        # your project-scoped token
# (or a [pypi] entry in ~/.pypirc). If missing, it prints this and exits without
# uploading. Idempotent: if this version is already on PyPI it reports success.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
PY="${PYTHON:-python}"
PKG="universal-wasm-loader"

ASSUME_YES=0
DRY_RUN=0
ALLOW_DIRTY=0
SKIP_TAG_CHECK=0
REMOTE="origin"

while [ $# -gt 0 ]; do
  case "$1" in
    --yes)            ASSUME_YES=1; shift ;;
    --dry-run)        DRY_RUN=1; shift ;;
    --allow-dirty)    ALLOW_DIRTY=1; shift ;;
    --skip-tag-check) SKIP_TAG_CHECK=1; shift ;;
    --remote)         REMOTE="${2:-}"; shift 2 ;;
    -h|--help)        sed -n '2,/^set -euo/p' "$0" | sed 's/^# \{0,1\}//; s/^#//'; exit 0 ;;
    *) echo "error: unknown argument: $1" >&2; exit 2 ;;
  esac
done

run() { echo "+ $*"; if [ "$DRY_RUN" -eq 0 ]; then "$@"; fi; }
# Fatal in a real run; downgraded to a warning under --dry-run so the flow is inspectable.
guard() { # guard <message>
  if [ "$DRY_RUN" -eq 1 ]; then echo "warning (ignored under --dry-run): $1" >&2; return 0; fi
  echo "error: $1" >&2; exit 1
}

# --- Version / tag (source of truth: pyproject.toml) ------------------------
VERSION="$(grep -m1 -oE '^version[[:space:]]*=[[:space:]]*"[^"]+"' pyproject.toml \
           | grep -oE '"[^"]+"' | tr -d '"')"
[ -n "$VERSION" ] || { echo "error: could not read version from pyproject.toml" >&2; exit 1; }
TAG="v$VERSION"
echo "Publishing $PKG $VERSION to PyPI"

# --- Preflight: clean tree --------------------------------------------------
if [ "$ALLOW_DIRTY" -eq 0 ] && [ -n "$(git status --porcelain)" ]; then
  guard "working tree is dirty — commit/stash, or pass --allow-dirty."
fi

# --- Preflight: the release tag exists locally and on the remote ------------
if [ "$SKIP_TAG_CHECK" -eq 0 ]; then
  git rev-parse -q --verify "refs/tags/$TAG" >/dev/null \
    || guard "tag $TAG not found locally — run scripts/release.sh first (or --skip-tag-check)."
  if ! git ls-remote --tags "$REMOTE" "$TAG" | grep -q "refs/tags/$TAG"; then
    guard "tag $TAG not on $REMOTE — push it (scripts/release.sh) before publishing (or --skip-tag-check)."
  fi
fi

# --- Idempotency: is this version already on PyPI? --------------------------
if curl -fsS "https://pypi.org/pypi/$PKG/$VERSION/json" >/dev/null 2>&1; then
  echo "$PKG $VERSION is already on PyPI — nothing to do."
  echo "(See https://pypi.org/project/$PKG/$VERSION/)"
  exit 0
fi

# --- Auth gate: need a PyPI token (env or ~/.pypirc) ------------------------
if [ -z "${TWINE_PASSWORD:-}" ] && [ ! -f "$HOME/.pypirc" ]; then
  guard "no PyPI credentials found. Set a token and re-run:
         export TWINE_USERNAME=__token__
         export TWINE_PASSWORD=pypi-XXXXXXXX   # your project-scoped PyPI token
       (or add a [pypi] entry to ~/.pypirc)."
fi
# Default the username to __token__ when a password/token is supplied without one.
if [ -n "${TWINE_PASSWORD:-}" ] && [ -z "${TWINE_USERNAME:-}" ]; then
  export TWINE_USERNAME="__token__"
fi

# --- Confirm (irreversible: a PyPI version can never be re-uploaded) --------
if [ "$ASSUME_YES" -eq 0 ] && [ "$DRY_RUN" -eq 0 ]; then
  printf "Upload %s %s to PyPI? This is irreversible. [y/N] " "$PKG" "$VERSION"
  read -r reply
  case "$reply" in [yY]|[yY][eE][sS]) ;; *) echo "Aborted."; exit 1 ;; esac
fi

# --- Build fresh, then upload -----------------------------------------------
run rm -rf dist
run "$PY" -m build
run "$PY" -m twine check dist/*
run "$PY" -m twine upload dist/*

if [ "$DRY_RUN" -eq 1 ]; then
  echo "Dry run complete — nothing built or uploaded; $PKG $VERSION was NOT published."
else
  echo "Done: published $PKG $VERSION to PyPI."
  echo "Verify at https://pypi.org/project/$PKG/$VERSION/"
fi
