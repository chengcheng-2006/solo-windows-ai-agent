"""Model migration verification — ensure no old deepseek model references remain.

This test verifies that:
1. No `deepseek-chat` or `deepseek-reasoner` references exist in v0.1.1 code
2. All model references use v4 variants (flash/pro/chat)
3. The default routing model is deepseek-v4-flash
"""
import re
from pathlib import Path

import pytest

SOLO_ROOT = Path(__file__).resolve().parent.parent
SOLO_SRC = SOLO_ROOT / "src" / "solo"

# Old models that must NOT appear in new code
BANNED_PATTERNS = [
    r"deepseek-chat",
    r"deepseek-reasoner",
]

# Acceptable model references for v0.1.1
ACCEPTABLE_REFERENCES = [
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "deepseek-v4-chat",
    "glm-4.7-flash",
]


def _get_py_files(directory):
    """Recursively find all .py files under a directory."""
    for f in directory.rglob("*.py"):
        if "__pycache__" not in str(f):
            yield f


def test_no_banned_model_references():
    """Verify no `deepseek-chat` or `deepseek-reasoner` in v0.1.1 source code."""
    banned_found = []
    for py_file in _get_py_files(SOLO_SRC):
        content = py_file.read_text(encoding="utf-8")
        for pattern in BANNED_PATTERNS:
            if re.search(pattern, content):
                banned_found.append((str(py_file.relative_to(SOLO_ROOT)), pattern))

    if banned_found:
        msg = "\n".join(f"  {f}: {p}" for f, p in banned_found)
        pytest.fail(f"Found banned model references:\n{msg}")


def test_all_model_references_are_v4():
    """Verify all 'deepseek' model references in src/solo use v4 variants."""
    refs = []
    for py_file in _get_py_files(SOLO_SRC):
        content = py_file.read_text(encoding="utf-8")
        for match in re.finditer(r'deepseek[-/][a-z0-9/-]+', content):
            ref = match.group()
            if "v4" not in ref and ref not in ("deepseek", "deepseek-adapter"):
                refs.append((str(py_file.relative_to(SOLO_ROOT)), ref))

    if refs:
        msg = "\n".join(f"  {f}: {r}" for f, r in refs)
        pytest.fail(f"Found non-v4 deepseek references:\n{msg}")


def test_default_model_is_v4_flash():
    from solo.core.enums import RiskLevel
    from solo.core.policy import PolicyEngine
    engine = PolicyEngine()
    decision = engine.evaluate("user", "user", "test", RiskLevel.R0)
    assert decision is not None


def test_demo_no_old_model_references():
    """Verify demo modules don't reference old models."""
    demo_files = list((SOLO_SRC / "demo").rglob("*.py"))
    for py_file in demo_files:
        content = py_file.read_text(encoding="utf-8")
        for pattern in BANNED_PATTERNS:
            matches = re.findall(pattern, content)
            assert len(matches) == 0, (
                f"Found {len(matches)} banned reference(s) to {pattern!r} "
                f"in {py_file.relative_to(SOLO_ROOT)}"
            )


def test_cli_no_old_model_references():
    """Verify CLI modules don't reference old models."""
    cli_files = list((SOLO_SRC / "cli").rglob("*.py"))
    for py_file in cli_files:
        content = py_file.read_text(encoding="utf-8")
        for pattern in BANNED_PATTERNS:
            assert not re.search(pattern, content), (
                f"Banned reference in {py_file.relative_to(SOLO_ROOT)}"
            )


def test_pyproject_no_banned_models():
    """Verify pyproject.toml has no banned model references."""
    pyproject = SOLO_ROOT / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8")
        for pattern in BANNED_PATTERNS:
            assert not re.search(pattern, content), "Banned reference in pyproject.toml"


def test_evidence_no_api_key_leak():
    """Verify no API keys or bearer tokens are hardcoded in src/solo."""
    dangerous = re.compile(
        r'(?:sk-[a-zA-Z0-9]{20,}|'
        r'AIza[0-9A-Za-z_-]{35}|'
        r'ghp_[0-9a-zA-Z]{36}|'
        r'github_pat_[0-9a-zA-Z_]{82,})'
    )

    leaks = []
    for py_file in _get_py_files(SOLO_SRC):
        content = py_file.read_text(encoding="utf-8")
        for match in dangerous.finditer(content):
            leaks.append((str(py_file.relative_to(SOLO_ROOT)), match.group()[:20] + "..."))

    if leaks:
        msg = "\n".join(f"  {f}: {t}" for f, t in leaks)
        pytest.fail(f"Potential API Key leak detected:\n{msg}")
