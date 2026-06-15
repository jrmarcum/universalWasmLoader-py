#!/usr/bin/env bash
# Release script — reads the version from pyproject.toml, tags vX.Y.Z, and pushes the
# tag so the GitHub Actions `publish.yml` workflow builds + uploads to PyPI.
#
# Never builds or uploads to PyPI locally — publishing happens only in CI (run:-only
# workflow). This mirrors the -js reference's `scripts/publish.ts` (`deno task publish`).
#
# Usage:
#   bash scripts/release.sh           # tag + push the current pyproject.toml version
#   bash scripts/release.sh --no-push # create the tag locally only (no push)
#
# Typical flow:
#   pixi run bump minor          # raise pyproject.toml version
#   git commit -am "bump version to vX.Y.Z"
#   bash scripts/release.sh      # tag + push -> CI publishes
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Extract the [project] version = "X.Y.Z" from pyproject.toml (first match).
VERSION="$(grep -m1 -E '^version[[:space:]]*=[[:space:]]*"[0-9]+\.[0-9]+\.[0-9]+"' pyproject.toml \
  | sed -E 's/^version[[:space:]]*=[[:space:]]*"([0-9]+\.[0-9]+\.[0-9]+)".*/\1/')"

if [ -z "${VERSION:-}" ]; then
  echo "❌ release: could not read version from pyproject.toml" >&2
  exit 1
fi

TAG="v${VERSION}"
echo "Releasing ${TAG} (from pyproject.toml version ${VERSION})…"

# Create/force the tag at HEAD.
git tag -f "${TAG}"

if [ "${1:-}" = "--no-push" ]; then
  echo "Tag ${TAG} created locally (--no-push). Push it with: git push origin ${TAG}"
  exit 0
fi

git push origin "${TAG}"
echo ""
echo "Tag ${TAG} pushed. GitHub Actions (publish.yml) will build + upload to PyPI."
