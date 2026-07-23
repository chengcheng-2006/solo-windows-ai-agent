from __future__ import annotations

from pathlib import Path

from .redaction import contains_secret


DANGEROUS_ACTION_WORDS = {
    "delete",
    "remove",
    "format disk",
    "format drive",
    "firewall",
    "admin",
    "administrator",
    "uac",
    "push",
    "merge",
    "release",
    "群聊",
    "转发",
}


def is_low_risk_action(description: str) -> bool:
    lower = description.lower()
    return not any(word.lower() in lower for word in DANGEROUS_ACTION_WORDS)


def ensure_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def scan_text_for_secret(path: Path) -> bool:
    try:
        return contains_secret(path.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return False
