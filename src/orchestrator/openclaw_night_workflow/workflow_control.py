from __future__ import annotations

import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .app import NightWorkflowOrchestrator
from .codex_adapter import CodexAdapter
from .config import get_settings
from .manifest import load_manifest
from .schemas import utc_now

WORKFLOW_ID = "openclaw-hermes-v1"
TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED"}
RUN_ID_RE = re.compile(r"^run-[a-f0-9]{12}$")
ACTION_ID_RE = re.compile(r"^act-[a-f0-9]{12}$")


class WorkflowControlError(ValueError):
    pass


def _read_openclaw_owner_allowlist() -> list[str]:
    path = Path(r"C:\Users\35331\.openclaw\openclaw.json")
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    values = data.get("commands", {}).get("ownerAllowFrom", [])
    if not values:
        values = data.get("security", {}).get("ownerAllowFrom", [])
    return [str(value) for value in values if isinstance(value, str)]


def _require_owner(owner_id: str | None) -> str:
    if not owner_id:
        raise WorkflowControlError("owner_id is required")
    allowed = _read_openclaw_owner_allowlist()
    if owner_id not in allowed:
        raise WorkflowControlError("caller is not an allowed owner")
    return owner_id


def _require_workflow(workflow_id: str) -> None:
    if workflow_id != WORKFLOW_ID:
        raise WorkflowControlError(f"unsupported workflow_id: {workflow_id}")


def _require_run_id(run_id: str | None) -> str:
    if not run_id or not RUN_ID_RE.match(run_id):
        raise WorkflowControlError("run_id must match run-<12 lowercase hex chars>")
    return run_id


def _require_action_id(action_id: str | None) -> str:
    if not action_id or not ACTION_ID_RE.match(action_id):
        raise WorkflowControlError("action_id must match act-<12 lowercase hex chars>")
    return action_id


def _connect_db(root: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(root / "database" / "night_workflows.db")
    conn.row_factory = sqlite3.Row
    return conn


def status(root: Path, workflow_id: str, owner_id: str | None) -> dict[str, Any]:
    _require_workflow(workflow_id)
    _require_owner(owner_id)
    settings = get_settings(root)
    orch = NightWorkflowOrchestrator(settings)
    try:
        health = orch.health()
    finally:
        orch.close()
    conn = _connect_db(root)
    try:
        rows = conn.execute(
            "SELECT run_id, state, current_phase_id, updated_at FROM workflow_runs WHERE workflow_id=? ORDER BY updated_at DESC LIMIT 20",
            (WORKFLOW_ID,),
        ).fetchall()
    finally:
        conn.close()
    active = [dict(row) for row in rows if row["state"] not in TERMINAL_STATES]
    running = [row for row in active if row["state"] in {"DISPATCHING", "RUNNING", "WAITING_FOR_COMPLETION", "VALIDATING", "RETRYING"}]
    return {
        "ok": True,
        "action": "status",
        "workflow_id": WORKFLOW_ID,
        "registered": True,
        "orchestrator_health": health,
        "active_runs": active,
        "running_count": len(running),
        "formal_phase_started": False,
        "correlation_id": uuid.uuid4().hex,
    }


def dry_run_start(root: Path, workflow_id: str, owner_id: str | None) -> dict[str, Any]:
    _require_workflow(workflow_id)
    _require_owner(owner_id)
    manifest_path = root / "workflow" / "manifests" / "openclaw_hermes_v1.json"
    manifest = load_manifest(manifest_path)
    prompt_checks = [
        {"path": phase["prompt_path"], "exists": (root / phase["prompt_path"]).exists()}
        for phase in manifest["phases"]
    ]
    validators = [
        root / "orchestrator" / "src" / "openclaw_night_workflow" / "validator_cli.py",
        root / "orchestrator" / "src" / "openclaw_night_workflow" / "validator_runner.py",
    ]
    validator_checks = [{"path": str(path.relative_to(root)).replace("\\", "/"), "exists": path.exists()} for path in validators]
    codex_health = CodexAdapter().health()
    ok = all(item["exists"] for item in prompt_checks) and all(item["exists"] for item in validator_checks) and codex_health.get("status") == "PASS"
    report = {
        "ok": ok,
        "action": "start",
        "dry_run": True,
        "workflow_id": WORKFLOW_ID,
        "manifest": str(manifest_path),
        "prompt_checks": prompt_checks,
        "validator_checks": validator_checks,
        "codex_harness_adapter": codex_health,
        "formal_phase_started": False,
        "created_running_task": False,
        "next_action_allowed": "STOP",
        "operator_message": "Dry-run completed. Do not ask to execute Phase 1, and do not start any formal phase from this registration flow.",
        "correlation_id": uuid.uuid4().hex,
        "checked_at": utc_now(),
    }
    out_dir = root / "evidence" / "dry_runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"openclaw-hermes-v1-dry-run-{uuid.uuid4().hex[:10]}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(out_path)
    return report


def transition(root: Path, workflow_id: str, owner_id: str | None, action: str, run_id: str | None) -> dict[str, Any]:
    _require_workflow(workflow_id)
    _require_owner(owner_id)
    rid = _require_run_id(run_id)
    orch = NightWorkflowOrchestrator(get_settings(root))
    try:
        if action == "pause":
            result = orch.pause_run(rid)
        elif action == "resume":
            result = orch.resume_run(rid)
        elif action == "cancel":
            result = orch.cancel_run(rid)
        else:
            raise WorkflowControlError(f"unsupported transition action: {action}")
    finally:
        orch.close()
    return {"ok": True, "action": action, "workflow_id": WORKFLOW_ID, **result, "correlation_id": uuid.uuid4().hex}


def resolve_action(root: Path, workflow_id: str, owner_id: str | None, action: str, action_id: str | None) -> dict[str, Any]:
    _require_workflow(workflow_id)
    _require_owner(owner_id)
    aid = _require_action_id(action_id)
    conn = _connect_db(root)
    try:
        row = conn.execute("SELECT * FROM approvals WHERE action_id=?", (aid,)).fetchone()
        if not row:
            raise WorkflowControlError("approval action_id not found")
        if row["status"] != "PENDING":
            raise WorkflowControlError("approval action_id is not pending")
        status_value = "APPROVED" if action == "approve" else "REJECTED"
        conn.execute("UPDATE approvals SET status=?, used_at=? WHERE action_id=? AND status='PENDING'", (status_value, utc_now(), aid))
        conn.commit()
        return {"ok": True, "action": action, "workflow_id": WORKFLOW_ID, "action_id": aid, "status": status_value, "correlation_id": uuid.uuid4().hex}
    finally:
        conn.close()


def export_evidence(root: Path, workflow_id: str, owner_id: str | None) -> dict[str, Any]:
    _require_workflow(workflow_id)
    _require_owner(owner_id)
    from .evidence import export_file_manifest

    out = root / "evidence" / "00_5_export_file_manifest.json"
    export_file_manifest(root, out)
    return {"ok": True, "action": "export", "workflow_id": WORKFLOW_ID, "path": str(out), "correlation_id": uuid.uuid4().hex}
