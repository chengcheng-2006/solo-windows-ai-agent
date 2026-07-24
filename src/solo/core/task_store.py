"""SQLite TaskStore for Solo v0.1.1 — lightweight, zero-dependency task persistence.

Lite mode DDL: workflow_runs, workflow_events, execution_attempts, validation_runs, approvals.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class TaskStore:
    """SQLite-backed task store for workflow persistence."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._conn: sqlite3.Connection | None = None

    # ── Connection management ──────────────────────────────────

    def connect(self) -> sqlite3.Connection:
        """Open or return existing database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self._path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> TaskStore:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        """Get connection, auto-opening if needed."""
        return self.connect()

    # ── Schema ─────────────────────────────────────────────────

    def migrate(self) -> None:
        """Create or migrate database schema."""
        conn = self.connect()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS workflow_runs (
                run_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'RECEIVED',
                idempotency_key TEXT UNIQUE,
                payload TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS workflow_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                state TEXT NOT NULL,
                ok INTEGER NOT NULL DEFAULT 1,
                detail TEXT DEFAULT '',
                payload TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id)
            );

            CREATE INDEX IF NOT EXISTS idx_events_run_id ON workflow_events(run_id);

            CREATE TABLE IF NOT EXISTS execution_attempts (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                phase_id TEXT NOT NULL,
                attempt INTEGER NOT NULL DEFAULT 1,
                executor TEXT NOT NULL,
                task_id TEXT,
                started_at TEXT,
                finished_at TEXT,
                exit_code INTEGER,
                payload TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id)
            );

            CREATE TABLE IF NOT EXISTS validation_runs (
                validation_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                phase_id TEXT NOT NULL,
                result TEXT NOT NULL DEFAULT 'PASS',
                checks_total INTEGER DEFAULT 0,
                checks_passed INTEGER DEFAULT 0,
                checks_failed INTEGER DEFAULT 0,
                payload TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id)
            );

            CREATE TABLE IF NOT EXISTS approvals (
                action_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                workflow_id TEXT NOT NULL,
                phase_id TEXT NOT NULL,
                risk TEXT NOT NULL,
                target TEXT NOT NULL,
                nonce TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                expires_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                used_at TEXT,
                FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id)
            );

            CREATE INDEX IF NOT EXISTS idx_approvals_run_id ON approvals(run_id);
        """)
        conn.commit()

    # ── Workflow Runs ──────────────────────────────────────────

    def create_workflow_run(
        self,
        workflow_id: str,
        *,
        idempotency_key: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> str:
        """Create a new workflow run and return its run_id."""
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        conn = self.conn
        conn.execute(
            "INSERT INTO workflow_runs (run_id, workflow_id, state, idempotency_key, payload) "
            "VALUES (?, ?, 'RECEIVED', ?, ?)",
            (run_id, workflow_id, idempotency_key, json.dumps(payload) if payload else None),
        )
        conn.commit()
        return run_id

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Get a workflow run by ID."""
        row = self.conn.execute(
            "SELECT * FROM workflow_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        if result.get("payload"):
            result["payload"] = json.loads(result["payload"])
        return result

    def transition_run(
        self,
        run_id: str,
        state: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Transition a run to a new state with optional payload."""
        conn = self.conn
        payload_json = json.dumps(payload) if payload else None
        conn.execute(
            "UPDATE workflow_runs SET state = ?, payload = ?, updated_at = datetime('now') "
            "WHERE run_id = ?",
            (state, payload_json, run_id),
        )
        conn.commit()

    def append_event(
        self,
        run_id: str,
        state: str,
        *,
        ok: bool = True,
        detail: str = "",
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Append an event to a run's event log."""
        conn = self.conn
        conn.execute(
            "INSERT INTO workflow_events (run_id, state, ok, detail, payload) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, state, 1 if ok else 0, detail, json.dumps(payload) if payload else None),
        )
        conn.commit()

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        """Get all events for a run."""
        rows = self.conn.execute(
            "SELECT * FROM workflow_events WHERE run_id = ? ORDER BY event_id",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Execution Attempts ─────────────────────────────────────

    def record_execution_attempt(
        self,
        run_id: str,
        phase_id: str,
        attempt: int,
        executor: str,
        task_id: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        exit_code: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Record an execution attempt."""
        conn = self.conn
        conn.execute(
            "INSERT INTO execution_attempts (run_id, phase_id, attempt, executor, task_id, "
            "started_at, finished_at, exit_code, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id, phase_id, attempt, executor, task_id,
                started_at.isoformat() if started_at else None,
                finished_at.isoformat() if finished_at else None,
                exit_code,
                json.dumps(payload) if payload else None,
            ),
        )
        conn.commit()

    # ── Validation ─────────────────────────────────────────────

    def record_validation(self, validation_data: dict[str, Any]) -> None:
        """Record a validation result."""
        conn = self.conn
        conn.execute(
            "INSERT INTO validation_runs (validation_id, run_id, phase_id, result, "
            "checks_total, checks_passed, checks_failed, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                validation_data.get("validation_id"),
                validation_data.get("run_id"),
                validation_data.get("phase_id"),
                validation_data.get("result", "PASS"),
                validation_data.get("checks_total", 0),
                validation_data.get("checks_passed", 0),
                validation_data.get("checks_failed", 0),
                json.dumps(validation_data),
            ),
        )
        conn.commit()

    # ── Approvals ──────────────────────────────────────────────

    def create_approval_record(
        self,
        action_id: str,
        run_id: str,
        workflow_id: str,
        phase_id: str,
        risk: str,
        target: str,
        nonce: str,
        expires_at: str | None = None,
    ) -> None:
        """Record a pending approval request."""
        conn = self.conn
        conn.execute(
            "INSERT INTO approvals (action_id, run_id, workflow_id, phase_id, risk, target, "
            "nonce, status, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)",
            (action_id, run_id, workflow_id, phase_id, risk, target, nonce, expires_at),
        )
        conn.commit()

    def resolve_approval_record(
        self,
        action_id: str,
        new_status: str,
    ) -> bool:
        """Resolve an approval to APPROVED or REJECTED. Returns True if updated."""
        conn = self.conn
        cursor = conn.execute(
            "UPDATE approvals SET status = ?, used_at = datetime('now') "
            "WHERE action_id = ? AND status = 'PENDING'",
            (new_status, action_id),
        )
        conn.commit()
        return cursor.rowcount > 0
