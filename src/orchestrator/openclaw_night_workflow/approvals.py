from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from .schemas import utc_now
from .task_store import TaskStore


def create_approval(store: TaskStore, workflow_id: str, run_id: str, phase_id: str | None, risk: str, target: str, ttl_seconds: int = 3600) -> dict[str, str]:
    action_id = f"act-{uuid.uuid4().hex[:12]}"
    nonce = secrets.token_urlsafe(16)
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
    store.conn.execute(
        "INSERT INTO approvals(action_id, workflow_id, run_id, phase_id, risk, target, nonce, expires_at, status, created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (action_id, workflow_id, run_id, phase_id, risk, target, nonce, expires_at, "PENDING", utc_now()),
    )
    store.conn.commit()
    return {"action_id": action_id, "nonce": nonce, "expires_at": expires_at}


def resolve_approval(store: TaskStore, action_id: str, nonce: str, approve: bool, owner_confirmed: bool = True) -> bool:
    row = store.conn.execute("SELECT * FROM approvals WHERE action_id=?", (action_id,)).fetchone()
    if not row or not owner_confirmed:
        return False
    if row["status"] != "PENDING" or row["nonce"] != nonce:
        return False
    if datetime.fromisoformat(str(row["expires_at"])) < datetime.now(timezone.utc):
        store.conn.execute("UPDATE approvals SET status='EXPIRED' WHERE action_id=?", (action_id,))
        store.conn.commit()
        return False
    status = "APPROVED" if approve else "REJECTED"
    store.conn.execute(
        "UPDATE approvals SET status=?, used_at=? WHERE action_id=? AND status='PENDING'",
        (status, utc_now(), action_id),
    )
    store.conn.commit()
    return True

