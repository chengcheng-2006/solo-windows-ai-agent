from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .task_store import TaskStore
from .schemas import utc_now


def acquire_lock(store: TaskStore, lock_name: str, owner: str, lease_seconds: int = 300) -> bool:
    now = datetime.now(timezone.utc)
    lease_until = (now + timedelta(seconds=lease_seconds)).isoformat()
    row = store.conn.execute("SELECT * FROM locks WHERE lock_name=?", (lock_name,)).fetchone()
    if row and datetime.fromisoformat(str(row["lease_until"])) > now and row["owner"] != owner:
        return False
    store.conn.execute(
        "INSERT OR REPLACE INTO locks(lock_name, owner, lease_until, updated_at) VALUES(?,?,?,?)",
        (lock_name, owner, lease_until, utc_now()),
    )
    store.conn.commit()
    return True


def release_lock(store: TaskStore, lock_name: str, owner: str) -> bool:
    cur = store.conn.execute("DELETE FROM locks WHERE lock_name=? AND owner=?", (lock_name, owner))
    store.conn.commit()
    return cur.rowcount == 1

