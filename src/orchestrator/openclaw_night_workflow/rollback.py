from __future__ import annotations

import json
from pathlib import Path

from .schemas import utc_now


def create_bootstrap_rollback(root: Path) -> Path:
    rollback_dir = root / "backups" / "phase0_bootstrap_rollback"
    rollback_dir.mkdir(parents=True, exist_ok=True)
    plan = {
        "schema_version": "1.0",
        "created_at": utc_now(),
        "scope": "Phase 0 bootstrap project files only",
        "production_openclaw_modified": False,
        "manual_steps": [
            "Stop orchestrator if running.",
            "Back up database/night_workflows.db if needed.",
            "Remove or archive orchestrator, workflow/manifests/openclaw_hermes_v1.json, validators, and phase0 scripts.",
            "No OpenClaw production configuration rollback is required because Phase 0 did not modify it.",
        ],
    }
    path = rollback_dir / "ROLLBACK_PLAN.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    script = rollback_dir / "rollback_phase0_bootstrap.ps1"
    script.write_text(
        "Set-StrictMode -Version Latest\n"
        "$ErrorActionPreference = 'Stop'\n"
        "Write-Host 'Phase 0 rollback is manual-preview only. No production OpenClaw files were modified.'\n"
        "exit 0\n",
        encoding="utf-8",
    )
    return path

