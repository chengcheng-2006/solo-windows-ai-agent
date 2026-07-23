from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_PHASE_KEYS = {
    "phase_id",
    "display_name",
    "prompt_path",
    "validator_command",
    "timeout_seconds",
    "max_retries",
    "retry_policy",
    "allowed_automatic_actions",
    "prohibited_actions",
    "expected_artifacts",
    "success_conditions",
    "user_action_patterns",
    "rollback_policy",
    "next_phase",
}


def load_manifest(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_manifest(data, path.parent.parent.parent)
    return data


def validate_manifest(data: dict[str, Any], root: Path | None = None) -> None:
    for key in ["schema_version", "workflow_id", "source_spec", "phases"]:
        if key not in data:
            raise ValueError(f"Manifest missing required key: {key}")
    if data.get("workflow_id") != "openclaw-hermes-v1":
        raise ValueError("Unexpected workflow_id")
    if not isinstance(data["phases"], list) or len(data["phases"]) != 3:
        raise ValueError("Manifest must register exactly three phases")
    seen = set()
    for phase in data["phases"]:
        missing = REQUIRED_PHASE_KEYS - set(phase)
        if missing:
            raise ValueError(f"Phase {phase.get('phase_id')} missing keys: {sorted(missing)}")
        if phase["phase_id"] in seen:
            raise ValueError(f"Duplicate phase_id: {phase['phase_id']}")
        seen.add(phase["phase_id"])
        if root is not None and not (root / phase["prompt_path"]).exists():
            raise ValueError(f"Prompt path does not exist: {phase['prompt_path']}")

