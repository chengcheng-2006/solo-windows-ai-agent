#!/usr/bin/env python3
"""Strict documentation contract validator.

Checks:
1. All local .md links in docs/ resolve to existing files
2. README quick-start commands are valid
3. Any error exits non-zero

Usage: python scripts/ci/validate_docs.py
"""
import re
import sys
from pathlib import Path


def main() -> int:
    root = Path(".").resolve()
    errors = 0

    # ── Collect all markdown files ──
    md_files = sorted(root.rglob("*.md"))
    exclude_patterns = {"node_modules", ".venv", "__pycache__", ".git", "venv"}
    md_files = [f for f in md_files if not any(p in f.parts for p in exclude_patterns)]

    # Existing file paths for link resolution
    existing = set()
    for f in root.rglob("*"):
        if f.is_file() and not any(p in f.parts for p in exclude_patterns):
            existing.add(f.resolve())

    # ── Check 1: Local markdown links ──
    link_pattern = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")

    for md_file in md_files:
        rel = md_file.relative_to(root)
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        for match in link_pattern.finditer(content):
            link_text, link_url = match.groups()

            # Only check relative file links (.md, .py, .toml, etc.)
            if not link_url.startswith("http") and not link_url.startswith("#") and not link_url.startswith("mailto:"):
                # Resolve relative to the markdown file's directory
                linked = (md_file.parent / link_url).resolve()

                # Try to resolve without anchor
                linked_no_anchor = linked
                if "#" in link_url:
                    linked_no_anchor = (md_file.parent / link_url.split("#")[0]).resolve()

                if not linked.exists() and not linked_no_anchor.exists():
                    # Try relative to repo root
                    alt = (root / link_url.split("#")[0]).resolve()
                    if not alt.exists():
                        print(f"::error file={rel},title=Broken Link::{rel}:{match.start()}: "
                              f"Link '{link_url}' (text: '{link_text}') does not resolve to an existing file")
                        errors += 1

    # ── Check 2: README commands exist ──
    readme = root / "README.md"
    if readme.exists():
        content = readme.read_text(encoding="utf-8")
        # Check that referenced CLI commands actually exist
        cmd_pattern = re.compile(r"`(solo (?:demo|doctor|version|cleanup|test)[ a-z-]*)`")
        for match in cmd_pattern.finditer(content):
            cmd = match.group(1)
            parts = cmd.split()
            if len(parts) >= 1 and parts[0] == "solo":
                # Just check it references a valid solo command
                valid_commands = {"solo", "demo", "doctor", "version", "cleanup", "test", "safe", "veto"}
                for p in parts:
                    if p not in valid_commands:
                        print(f"::error file=README.md,title=Unknown Command::"
                              f"Unknown command '{cmd}' found in README.md")
                        errors += 1

    if errors:
        print(f"::error::Found {errors} documentation contract violations")
    else:
        print(f"[OK] {len(md_files)} markdown files checked, 0 link errors")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
