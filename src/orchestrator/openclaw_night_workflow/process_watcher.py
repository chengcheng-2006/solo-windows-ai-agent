from __future__ import annotations

import json
from pathlib import Path

from .redaction import contains_secret


def read_completion(summary_path: Path) -> dict:
    return json.loads(summary_path.read_text(encoding="utf-8"))


def inspect_completion(summary_path: Path, timeout_seconds: int | None = None) -> dict[str, object]:
    if not summary_path.exists():
        return {"complete": False, "reason": "summary_missing"}
    payload = read_completion(summary_path)
    text = summary_path.read_text(encoding="utf-8", errors="ignore")
    if "[USER ACTION REQUIRED]" in text or payload.get("user_action_required"):
        return {"complete": True, "requires_user_action": True, "reason": "user_action_required"}
    if contains_secret(text):
        return {"complete": True, "suspected_security_issue": True, "reason": "secret_detected"}
    if payload.get("exit_code", 1) != 0:
        return {"complete": True, "reason": "nonzero_exit", "exit_code": payload.get("exit_code")}
    return {"complete": True, "reason": "finished", "exit_code": 0}

