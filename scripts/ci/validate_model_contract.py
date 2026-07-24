#!/usr/bin/env python3
"""Model contract validator — verify no old model references exist in source code.

Checks for banned patterns in src/ (source code only, not docs or test fixtures).
Checks:
1. No `deepseek-chat` or `deepseek-reasoner` in src/
2. No `zhipu/glm` in src/
3. No `glm-4.6v` in src/
"""
import re
import sys
from pathlib import Path

# Files that are known to contain banned patterns for testing/reporting purposes
_ALLOWED_FILES = {
    "config/examples/solo_model_routing.yaml",
    "tests/test_model_migration.py",
    "scripts/ci/validate_model_contract.py",
    "docs/internal/V011_RELEASE_GATE_REPORT.md",
    "docs/internal/V011_REMOTE_CI_FAILURE_ANALYSIS.md",
}

# Patterns that are NOT allowed in production source code
_BANNED_PATTERNS = [
    "deepseek-chat",
    "deepseek-reasoner",
    "zhipu/glm",
    "glm-4.6v",
    "glm-4.6v-flash",
]


def scan(root: str) -> list[tuple[str, str, int]]:
    """Scan src/ directory for banned patterns."""
    findings = []
    root_path = Path(root).resolve()
    exclude_dirs = {"node_modules", ".venv", "__pycache__", ".git", "venv"}

    for f in sorted(root_path.rglob("*")):
        if f.suffix not in (".py", ".toml", ".yaml", ".yml", ".json"):
            continue
        if not f.is_file():
            continue
        try:
            rel = str(f.relative_to(root_path))
        except ValueError:
            rel = str(f.relative_to(root_path.parent))
        if any(p in f.parts for p in exclude_dirs):
            continue
        # Only check src/ directory for production code
        if not rel.startswith("src/"):
            continue
        if rel in _ALLOWED_FILES:
            continue

        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            continue

        for pattern in _BANNED_PATTERNS:
            for match in re.finditer(re.escape(pattern), content):
                findings.append((rel, pattern, match.start()))

    return findings


def main() -> int:
    root = "."
    errors = len(scan(root))

    if errors:
        print(f"::error::Found {errors} model contract violations in src/ code")
    else:
        print("[OK] deepseek-chat | deepseek-reasoner: 0 matches in src/")
        print("[OK] zhipu/glm | glm-4.6v: 0 matches in src/")
        print("[OK] Model contract: all checks passed")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
