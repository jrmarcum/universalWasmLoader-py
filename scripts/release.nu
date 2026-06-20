#!/usr/bin/env nu
# Cut a release of universalWasmLoader-py consistently (cross-platform).
#
# Sibling of release.sh. The single source of truth for the version is
# `[project] version` in pyproject.toml. This tags the current commit
# `v<version>`, pushes the branch and tag to `origin`, and (unless --no-release)
# creates the matching GitHub Release. It does NOT publish to PyPI — that's
# publish.nu.
#
# Usage: nu scripts/release.nu [flags]

# Read the version from pyproject.toml (single source of truth).
def read-version []: nothing -> string {
  let parsed = (open --raw pyproject.toml | parse --regex '(?m)^version\s*=\s*"(?<v>[^"]+)"')
  if ($parsed | is-empty) {
    print -e "error: could not read version from pyproject.toml"
    exit 1
  }
  $parsed | get v.0
}

def main [
  --notes: string = ""    # Release notes body (default: a generic line)
  --no-release            # Push the tag only; skip creating a GitHub Release
  --no-build              # Skip the fresh `python -m build` verification
  --remote: string = "origin"
  --dry-run               # Print what would happen; make no tags/pushes/releases
] {
  let py = ($env.PYTHON? | default "python")
  let version = (read-version)
  let tag = $"v($version)"
  print $"Releasing ($tag) \(from pyproject.toml)"

  # Preflight: clean tree.
  let status = (^git status --porcelain)
  if ($status | str trim | is-not-empty) {
    print -e "error: working tree is dirty — commit or stash before releasing."
    print -e $status
    exit 1
  }

  let branch = (^git rev-parse --abbrev-ref HEAD | str trim)
  print $"On branch: ($branch)"

  # If the tag already exists, it must point at the current commit.
  let head = (^git rev-parse HEAD | str trim)
  let tag_exists = (^git rev-parse -q --verify $"refs/tags/($tag)" | complete).exit_code == 0
  if $tag_exists {
    let tagcommit = (^git rev-parse $"($tag)^{commit}" | str trim)
    if $tagcommit != $head {
      print -e $"error: tag ($tag) exists but does not point at HEAD."
      print -e "       Bump the version in pyproject.toml or move the tag deliberately."
      exit 1
    }
    print $"tag ($tag) already exists at HEAD — reusing."
  }

  # Verify it builds (fresh sdist + wheel).
  if not $no_build {
    print "Verifying build (fresh sdist + wheel)…"
    print "+ rm -rf dist"
    if not $dry_run { rm --recursive --force dist }
    print $"+ ($py) -m build"
    if not $dry_run { ^$py -m build }
  }

  # Tag.
  if not $tag_exists {
    print $"+ git tag -a ($tag) -m \"universalWasmLoader-py ($tag)\""
    if not $dry_run { ^git tag -a $tag -m $"universalWasmLoader-py ($tag)" }
  }

  # Push branch + tag.
  print $"+ git push ($remote) ($branch)"
  if not $dry_run { ^git push $remote $branch }
  print $"+ git push ($remote) ($tag)"
  if not $dry_run { ^git push $remote $tag }

  # GitHub Release.
  if not $no_release {
    if (which gh | is-empty) {
      print -e "warning: gh CLI not found — skipping GitHub Release (tag is pushed)."
    } else if (^gh auth status | complete).exit_code != 0 {
      print -e "warning: gh is not authenticated — skipping GitHub Release (tag is pushed)."
      print -e $"         Run 'gh auth login' \(or set GH_TOKEN), then: gh release create ($tag)"
    } else if (^gh release view $tag | complete).exit_code == 0 {
      print $"GitHub Release ($tag) already exists — leaving it untouched."
    } else {
      let body = (if ($notes | is-empty) {
        $"Release ($tag) of universalWasmLoader-py — Python port of the Universal WASM Loader."
      } else { $notes })
      print $"+ gh release create ($tag) --title ($tag) --notes <body>"
      if not $dry_run { ^gh release create $tag --title $tag --notes $body }
    }
  }

  print $"Done: ($tag)"
  print "To publish to PyPI (separate, deliberate step): nu scripts/publish.nu"
}
