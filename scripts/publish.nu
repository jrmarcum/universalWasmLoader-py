#!/usr/bin/env nu
# Publish this package to PyPI — a SEPARATE, deliberate step (cross-platform
# sibling of publish.sh), intentionally kept out of release.nu (PyPI uploads are
# irreversible: a version can never be re-uploaded).
#
# Reads the version from pyproject.toml, requires the matching v<version> tag to
# already exist locally AND on the remote, runs a fresh `python -m build`, and
# uploads with `twine`.
#
# Prereq order:  bump-version.nu -> release.nu -> publish.nu
#
# Usage: nu scripts/publish.nu [flags]
# Auth-gated: needs a PyPI API token in the environment —
#   $env.TWINE_USERNAME = "__token__"
#   $env.TWINE_PASSWORD = "pypi-XXXXXXXX"   # your project-scoped token
# (or a [pypi] entry in ~/.pypirc).

# Read the version from pyproject.toml (single source of truth).
def read-version []: nothing -> string {
  let parsed = (open --raw pyproject.toml | parse --regex '(?m)^version\s*=\s*"(?<v>[^"]+)"')
  if ($parsed | is-empty) {
    print -e "error: could not read version from pyproject.toml"
    exit 1
  }
  $parsed | get v.0
}

# Fatal in a real run; downgraded to a warning under --dry-run so the flow is inspectable.
def guard [dry: bool, msg: string] {
  if $dry {
    print -e $"warning \(ignored under --dry-run): ($msg)"
  } else {
    print -e $"error: ($msg)"
    exit 1
  }
}

def main [
  --yes             # Don't prompt for confirmation before uploading
  --dry-run         # Print the build + upload commands; run nothing
  --allow-dirty     # Skip the clean-working-tree check
  --skip-tag-check  # Don't require the v<version> tag locally + on remote
  --remote: string = "origin"
] {
  let py = ($env.PYTHON? | default "python")
  let pkg = "universal-wasm-loader"
  let version = (read-version)
  let tag = $"v($version)"
  print $"Publishing ($pkg) ($version) to PyPI"

  # Preflight: clean tree.
  if not $allow_dirty {
    let status = (^git status --porcelain)
    if ($status | str trim | is-not-empty) {
      guard $dry_run "working tree is dirty — commit/stash, or pass --allow-dirty."
    }
  }

  # Preflight: the release tag exists locally and on the remote.
  if not $skip_tag_check {
    if (^git rev-parse -q --verify $"refs/tags/($tag)" | complete).exit_code != 0 {
      guard $dry_run $"tag ($tag) not found locally — run scripts/release.nu first \(or --skip-tag-check)."
    }
    let lsr = (^git ls-remote --tags $remote $tag | complete)
    if not ($lsr.stdout | str contains $"refs/tags/($tag)") {
      guard $dry_run $"tag ($tag) not on ($remote) — push it \(scripts/release.nu) before publishing \(or --skip-tag-check)."
    }
  }

  # Idempotency: is this version already on PyPI?
  mut already = false
  try {
    http get $"https://pypi.org/pypi/($pkg)/($version)/json" | ignore
    $already = true
  } catch { }
  if $already {
    print $"($pkg) ($version) is already on PyPI — nothing to do."
    print $"\(See https://pypi.org/project/($pkg)/($version)/)"
    exit 0
  }

  # Auth gate: need a PyPI token (env or ~/.pypirc).
  let has_pypirc = ("~/.pypirc" | path expand | path exists)
  if ($env.TWINE_PASSWORD? | is-empty) and (not $has_pypirc) {
    guard $dry_run "no PyPI credentials found. Set a token and re-run:
         $env.TWINE_USERNAME = \"__token__\"
         $env.TWINE_PASSWORD = \"pypi-XXXXXXXX\"   # your project-scoped PyPI token
       (or add a [pypi] entry to ~/.pypirc)."
  }
  # Default the username to __token__ when a password/token is supplied without one.
  if ($env.TWINE_PASSWORD? | is-not-empty) and ($env.TWINE_USERNAME? | is-empty) {
    $env.TWINE_USERNAME = "__token__"
  }

  # Confirm (irreversible: a PyPI version can never be re-uploaded).
  if (not $yes) and (not $dry_run) {
    let reply = (input $"Upload ($pkg) ($version) to PyPI? This is irreversible. [y/N] ")
    if not (($reply | str downcase | str trim) in ["y" "yes"]) {
      print "Aborted."
      exit 1
    }
  }

  # Build fresh, then upload. This is a pixi project, so build/publish run inside
  # the pixi env (which provides `build` + `twine`). Auto-detected when a
  # pixi.toml + the pixi CLI are present; force with $env.UWL_PY_TOOL = "pixi" | "python".
  let force = ($env.UWL_PY_TOOL? | default "")
  let use_pixi = (if $force == "pixi" { true } else if $force == "python" { false } else { (("pixi.toml" | path exists) and (which pixi | is-not-empty)) })

  print "+ rm -rf dist"
  if not $dry_run { rm --recursive --force dist }

  if $use_pixi {
    print "+ pixi run python -m build"
    if not $dry_run { ^pixi run python -m build }
    print "+ pixi run python -m twine check dist/*"
    if not $dry_run { ^pixi run python -m twine check ...(glob dist/*) }
    print "+ pixi run python -m twine upload dist/*"
    if not $dry_run { ^pixi run python -m twine upload ...(glob dist/*) }
  } else {
    print $"+ ($py) -m build"
    if not $dry_run { ^$py -m build }
    print $"+ ($py) -m twine check dist/*"
    if not $dry_run { ^$py -m twine check ...(glob dist/*) }
    print $"+ ($py) -m twine upload dist/*"
    if not $dry_run { ^$py -m twine upload ...(glob dist/*) }
  }

  if $dry_run {
    print $"Dry run complete — nothing built or uploaded; ($pkg) ($version) was NOT published."
  } else {
    print $"Done: published ($pkg) ($version) to PyPI."
    print $"Verify at https://pypi.org/project/($pkg)/($version)/"
  }
}
