"""Approval engine — create and resolve approval requests with nonce-based verification."""
from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from .task_store import TaskStore


def _generate_nonce() -> str:
    """Generate a cryptographic nonce for approval verification."""
    return secrets.token_hex(32)


def _now_iso() -> str:
    """Current UTC time as ISO string."""
    return datetime.now(UTC).isoformat()


def create_approval(
    store: TaskStore,
    workflow_id: str,
    run_id: str,
    phase_id: str,
    risk: str,
    target: str,
    ttl_seconds: int = 300,
) -> dict[str, Any]:
    """Create a new approval request with nonce.

    Returns dict with action_id, nonce, expires_at.
    """
    action_id = f"act-{uuid.uuid4().hex[:12]}"
    nonce = _generate_nonce()
    expires_at = (datetime.now(UTC) + timedelta(seconds=ttl_seconds)).isoformat()

    store.create_approval_record(
        action_id=action_id,
        run_id=run_id,
        workflow_id=workflow_id,
        phase_id=phase_id,
        risk=risk,
        target=target,
        nonce=nonce,
        expires_at=expires_at,
    )

    return {
        "action_id": action_id,
        "nonce": nonce,
        "expires_at": expires_at,
    }


def resolve_approval(
    store: TaskStore,
    action_id: str,
    nonce: str,
    approve: bool,
    owner_confirmed: bool = True,
) -> bool:
    """Resolve an approval. Verifies nonce before updating.

    Returns True if resolution was applied.
    Verification steps:
    1. Check approval exists and is PENDING
    2. Verify nonce matches (cryptographic binding)
    3. Update status to APPROVED or REJECTED
    """
    # Fetch the approval record
    row = store.conn.execute(
        "SELECT * FROM approvals WHERE action_id = ?", (action_id,)
    ).fetchone()

    if row is None:
        return False

    if row["status"] != "PENDING":
        return False

    # Verify nonce
    if row["nonce"] != nonce:
        return False

    if not owner_confirmed:
        return False

    new_status = "APPROVED" if approve else "REJECTED"
    return store.resolve_approval_record(action_id, new_status)
