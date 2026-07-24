#!/usr/bin/env python3
"""Strict YAML validator — parse all .yaml/.yml files with PyYAML.

Usage: python scripts/ci/validate_yaml.py [directory]

Returns exit code 0 if all YAML files are valid, 1 otherwise.
"""
import os
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("::error::PyYAML is required. Run: pip install pyyaml")
    sys.exit(1)


def main(root: str = ".") -> int:
    errors = 0
    root_path = Path(root).resolve()
    exclude_patterns = {"node_modules", ".venv", "__pycache__", ".git", "venv"}

    for yaml_file in sorted(root_path.rglob("*")):
        if yaml_file.suffix not in (".yaml", ".yml"):
            continue
        try:
            rel = yaml_file.relative_to(root_path)
        except ValueError:
            rel = yaml_file.relative_to(root_path.parent)
        if any(p in yaml_file.parts for p in exclude_patterns):
            continue

        try:
            raw = yaml_file.read_text(encoding="utf-8")
            parsed = yaml.safe_load(raw)
            if parsed is None and raw.strip():
                # File has content but parsed to None — might be valid empty doc
                pass
        except yaml.YAMLError as exc:
            print(f"::error file={rel},title=YAML Syntax Error::{rel}: {exc}")
            errors += 1
        except Exception as exc:
            print(f"::error file={rel},title=YAML Parse Error::{rel}: {exc}")
            errors += 1

    if errors:
        print(f"::error::Found {errors} YAML file(s) with syntax errors")
    else:
        yaml_count = sum(1 for f in root_path.rglob("*") if f.suffix in (".yaml", ".yml")
                         and not any(p in f.parts for p in exclude_patterns))
        print(f"[OK] {yaml_count} YAML files validated, 0 errors")

    return 1 if errors else 0


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    sys.exit(main(root))
