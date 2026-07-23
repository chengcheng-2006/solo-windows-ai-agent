"""VETO Demo — R3 high-risk request rejected by safety system.

Demonstrates the safety mechanism: R3 classification → approval required →
reviewer rejects → REJECTED terminal state with 6 security guarantees.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..core.approvals import create_approval, resolve_approval
from ..core.enums import RiskLevel
from ..core.policy import PolicyEngine
from ..core.risk import RiskClassifier
from ..core.state_machine import can_transition
from ..core.task_store import TaskStore


R3_HAZARDOUS_REQUEST = "Delete all files in the important project directory"


def run_veto_demo(workspace: Path) -> dict[str, Any]:
    """Run the VETO Demo pipeline: R3 request → REJECTED.

    Returns structured result with pipeline events and security guarantees.
    """
    store = TaskStore(workspace / "demo.db")
    store.migrate()
    classifier = RiskClassifier()
    policy_engine = PolicyEngine()

    events: list[dict[str, Any]] = []

    # Step 1: RECEIVED
    task_id = store.create_workflow_run(
        "solo-veto-demo",
        idempotency_key="veto-demo-001",
    )
    store.append_event(task_id, "RECEIVED", detail="Hazardous request received")
    events.append({"state": "RECEIVED", "task_id": task_id})

    # Step 2: TRIAGED — Classify as R3
    risk = classifier.classify(R3_HAZARDOUS_REQUEST, task_type="file_operation")
    assert risk.level == RiskLevel.R3, f"Expected R3, got {risk.level}"

    policy = policy_engine.evaluate(
        requester="demo-owner",
        owner_id="demo-owner",
        source_channel="demo",
        risk=risk.level,
    )
    assert policy.allowed, "R3 should be allowed but require step-level approval"
    assert policy.requires_approval, "R3 requires approval"
    assert policy.approval_scope == "step", "R3 requires per-step approval"

    store.transition_run(task_id, "TRIAGED", payload={
        "risk": "R3",
        "reasons": list(risk.reasons),
        "policy": {
            "allowed": policy.allowed,
            "requires_approval": policy.requires_approval,
            "approval_scope": policy.approval_scope,
        },
    })
    store.append_event(
        task_id, "TRIAGED",
        ok=True,
        detail=f"🚨 R3: {risk.reasons[0] if risk.reasons else 'high_risk'}",
    )
    events.append({
        "state": "TRIAGED",
        "risk": "R3",
        "requires_approval": True,
    })

    # Step 3: REVIEW_PENDING — Create approval
    store.transition_run(task_id, "REVIEW_PENDING")

    approval = create_approval(
        store=store,
        workflow_id="solo-veto-demo",
        run_id=task_id,
        phase_id="demo-review",
        risk="R3",
        target=R3_HAZARDOUS_REQUEST,
        ttl_seconds=300,
    )
    events.append({
        "state": "REVIEW_PENDING",
        "action_id": approval["action_id"],
        "nonce_prefix": approval["nonce"][:8] + "...",
    })

    # Step 4: REJECTED — Reviewer rejects the request
    resolved = resolve_approval(
        store=store,
        action_id=approval["action_id"],
        nonce=approval["nonce"],
        approve=False,  # ← Reject!
        owner_confirmed=True,
    )
    assert resolved, "Approval rejection should succeed"

    store.transition_run(task_id, "REJECTED", payload={
        "action_id": approval["action_id"],
        "verdict": "REJECTED",
        "reason": "R3_high_risk_operation_denied_by_reviewer",
    })
    store.append_event(task_id, "REJECTED", ok=False, detail="Reviewer REJECTED the request")
    events.append({"state": "REJECTED", "verdict": "VETO"})

    # ── Security Guarantees Verification ──
    # 1. R3 correctly classified
    guarantee_r3_correct = risk.level == RiskLevel.R3

    # 2. Step-level approval required
    guarantee_approval_required = policy.requires_approval and policy.approval_scope == "step"

    # 3. Approval rejected by reviewer
    approval_row = store.conn.execute(
        "SELECT status FROM approvals WHERE action_id = ?",
        (approval["action_id"],),
    ).fetchone()
    guarantee_rejected = approval_row is not None and approval_row["status"] == "REJECTED"

    # 4. REJECTED is terminal
    guarantee_terminal = not can_transition("REJECTED", "DISPATCHED") and not can_transition("REJECTED", "EXECUTING")

    # 5. No execution attempts recorded
    attempt_count = store.conn.execute(
        "SELECT COUNT(*) as c FROM execution_attempts WHERE run_id = ?",
        (task_id,),
    ).fetchone()["c"]
    guarantee_no_execution = attempt_count == 0

    # 6. Nonce consumed
    guarantee_nonce_consumed = approval_row is not None and approval_row["status"] != "PENDING"

    security_guarantees = {
        "R3_correctly_classified": guarantee_r3_correct,
        "step_level_approval_required": guarantee_approval_required,
        "approval_rejected_by_reviewer": guarantee_rejected,
        "state_is_terminal": guarantee_terminal,
        "no_execution_occurred": guarantee_no_execution,
        "approval_nonce_consumed": guarantee_nonce_consumed,
    }

    store.close()

    return {
        "task_id": task_id,
        "mode": "lite",
        "status": "PASS",
        "risk_level": "R3",
        "risk_reasons": list(risk.reasons),
        "vetoed": True,
        "pipeline": events,
        "security_guarantees": security_guarantees,
    }
