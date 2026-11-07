#!/usr/bin/env python3
"""
prune_private.py: delete everything that should not be on the web, at deploy time.

Netlify runs this as the build command (see netlify.toml) inside its own
checkout of the repo, just before it publishes the repo root. Nothing in git
changes; only the deployed copy is trimmed.

Why not just _redirects? Netlify serves static files case-insensitively but
matches _redirects rules case-sensitively, so a rule for /PublishInstructions.md
does not stop /publishinstructions.md. Deleting the file is the only block that
cannot be bypassed.

The rule is default-deny: a file is published only if its extension is on
PUBLIC_EXTENSIONS and nothing below excludes it. Adding a new kind of public
file (say .webm video) means adding its extension here.

Usage:
  python3 scripts/prune_private.py            # delete (what Netlify runs)
  python3 scripts/prune_private.py --dry-run  # list what would be deleted
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parent.parent

PUBLIC_EXTENSIONS = {
    ".html", ".css", ".js", ".xml",
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".woff", ".woff2",
}

# Netlify config files: read before this runs, and never served.
KEEP_ANYWAY = {"_redirects", "_headers", "robots.txt"}

# Whole directories that are tooling, not site.
PRIVATE_DIRS = {"scripts", "n8n", "MyPubs-PDFs"}

# Files with a public extension that are still not pages.
PRIVATE_FILES = {"article-template.html"}


def is_private(rel: Path) -> bool:
    if rel.parts[0] in PRIVATE_DIRS:
        return True
    name = rel.name
    if len(rel.parts) == 1 and name in KEEP_ANYWAY:
        return False
    if name in PRIVATE_FILES:
        return True
    if name.startswith("_"):          # templates and authoring guides
        return True
    return rel.suffix.lower() not in PUBLIC_EXTENSIONS


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    removed: list[str] = []
    for top in sorted(SITE_ROOT.iterdir()):
        if top.name.startswith("."):   # .git etc.; Netlify never serves dotfiles
            continue
        if top.is_dir() and top.name in PRIVATE_DIRS:
            removed.append(f"{top.name}/")
            if not args.dry_run:
                shutil.rmtree(top)
            continue
        paths = [top] if top.is_file() else sorted(p for p in top.rglob("*") if p.is_file())
        for p in paths:
            rel = p.relative_to(SITE_ROOT)
            if any(part.startswith(".") for part in rel.parts):
                continue
            if is_private(rel):
                removed.append(rel.as_posix())
                if not args.dry_run:
                    p.unlink()

    verb = "Would remove" if args.dry_run else "Removed"
    print(f"{verb} {len(removed)} private path(s) from the deploy:")
    for r in removed:
        print(f"  {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
