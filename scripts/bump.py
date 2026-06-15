#!/usr/bin/env python3
"""Increment the ``version`` field in ``pyproject.toml``.

Mirrors the ``-js`` reference's ``scripts/bump.ts`` (``deno task bump``) UX, but for the
Python port: ``pyproject.toml`` is the single source of truth for the version.

Run via::

    pixi run bump            # patch:  0.1.0 -> 0.1.1   (default)
    pixi run bump minor      # minor:  0.1.0 -> 0.2.0
    pixi run bump major      # major:  0.1.0 -> 1.0.0

    # or directly, without pixi:
    python scripts/bump.py [patch|minor|major]

Pass ``--dry-run`` to print the next version WITHOUT writing the file (used by CI/validation
to prove the computation without mutating the tree).

This RAISES the ``pyproject.toml`` version. The tag-and-push step (``scripts/release.sh``)
reads the resulting version back out and tags ``vX.Y.Z`` so the publish workflow fires.

No third-party dependencies — uses only the stdlib so it runs on a bare ``python``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Make emoji-bearing output safe on legacy Windows consoles (cp1252) as well as
# UTF-8 CI runners — otherwise printing ✅ raises UnicodeEncodeError on Windows.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass

# scripts/ -> repo root
ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"

# Match the FIRST `version = "X.Y.Z"` (the one under [project]); pyproject's [project]
# table comes before any other version-like field.
VERSION_RE = re.compile(r'(?m)^(version\s*=\s*)"(\d+)\.(\d+)\.(\d+)"')


def main() -> int:
    args = [a for a in sys.argv[1:]]
    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]

    kind = (args[0] if args else "patch").lower()
    if kind not in ("patch", "minor", "major"):
        print(f'❌ bump: unknown release kind "{kind}" — use patch | minor | major',
              file=sys.stderr)
        return 1

    text = PYPROJECT.read_text(encoding="utf-8")
    m = VERSION_RE.search(text)
    if not m:
        print('❌ bump: could not find a `version = "X.Y.Z"` field in pyproject.toml',
              file=sys.stderr)
        return 1

    major, minor, patch = int(m.group(2)), int(m.group(3)), int(m.group(4))
    frm = f"{major}.{minor}.{patch}"
    if kind == "major":
        major, minor, patch = major + 1, 0, 0
    elif kind == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    to = f"{major}.{minor}.{patch}"

    if dry_run:
        print(to)
        return 0

    # Targeted replace so the rest of pyproject.toml's formatting is untouched.
    updated = VERSION_RE.sub(lambda _m: f'{_m.group(1)}"{to}"', text, count=1)
    PYPROJECT.write_text(updated, encoding="utf-8")
    print(f"✅ pyproject.toml → {to}  ({kind} bump from {frm})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
