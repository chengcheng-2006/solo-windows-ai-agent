from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .schemas import utc_now
from .state_machine import require_transition


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS workflow_runs (
  run_id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL,
  state TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  current_phase_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS phase_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  state TEXT NOT NULL,
  result TEXT,
  attempt INTEGER NOT NULL DEFAULT 0,
  started_at TEXT,
  finished_at TEXT,
  UNIQUE(run_id, phase_id, attempt)
);
CREATE TABLE IF NOT EXISTS workflow_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT NOT NULL,
  workflow_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  phase_id TEXT,
  correlation_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS execution_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  attempt INTEGER NOT NULL,
  executor TEXT NOT NULL,
  task_id TEXT NOT NULL,
  process_id TEXT,
  exit_code INTEGER,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  summary_path TEXT,
  log_path TEXT,
  user_action_required INTEGER NOT NULL DEFAULT 0,
  suspected_security_issue INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS validation_runs (
  validation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  phase_id TEXT NOT NULL,
  result TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
  action_id TEXT PRIMARY KEY,
  workflow_id TEXT NOT NULL,
  run_id TEXT NOT NULL,
  phase_id TEXT,
  risk TEXT NOT NULL,
  target TEXT NOT NULL,
  nonce TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  status TEXT NOT NULL,
  used_at TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  phase_id TEXT,
  path TEXT NOT NULL,
  sha256 TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  phase_id TEXT,
  target TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS locks (
  lock_name TEXT PRIMARY KEY,
  owner TEXT NOT NULL,
  lease_until TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS health_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  component TEXT NOT NULL,
  status TEXT NOT NULL,
  checked_at TEXT NOT NULL,
  payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rollback_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  reason TEXT NOT NULL,
  plan_path TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


class TaskStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        self.conn.close()

    def migrate(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def create_workflow_run(self, workflow_id: str, idempotency_key: str) -> str:
        row = self.conn.execute(
            "SELECT run_id FROM workflow_runs WHERE idempotency_key=?", (idempotency_key,)
        ).fetchone()
        if row:
            return str(row["run_id"])
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        now = utc_now()
        self.conn.execute(
            "INSERT INTO workflow_runs(run_id, workflow_id, state, idempotency_key, created_at, updated_at) VALUES(?,?,?,?,?,?)",
            (run_id, workflow_id, "CREATED", idempotency_key, now, now),
        )
        self.append_event(workflow_id, run_id, None, "workflow.created", {"idempotency_key": idempotency_key})
        self.conn.commit()
        return run_id

    def get_run(self, run_id: str) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM workflow_runs WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            raise KeyError(run_id)
        return row

    def transition_run(self, run_id: str, desired_state: str, phase_id: str | None = None, payload: dict[str, Any] | None = None) -> None:
        row = self.get_run(run_id)
        require_transition(str(row["state"]), desired_state)
        now = utc_now()
        self.conn.execute(
            "UPDATE workflow_runs SET state=?, current_phase_id=COALESCE(?, current_phase_id), updated_at=? WHERE run_id=?",
            (desired_state, phase_id, now, run_id),
        )
        self.append_event(str(row["workflow_id"]), run_id, phase_id, f"workflow.state.{desired_state.lower()}", payload or {})
        self.conn.commit()

    def append_event(self, workflow_id: str, run_id: str, phase_id: str | None, event_type: str, payload: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT INTO workflow_events(timestamp, workflow_id, run_id, phase_id, correlation_id, event_type, payload_json) VALUES(?,?,?,?,?,?,?)",
            (utc_now(), workflow_id, run_id, phase_id, uuid.uuid4().hex, event_type, json.dumps(payload, ensure_ascii=False)),
        )

    def record_execution_attempt(self, run_id: str, phase_id: str, attempt: int, executor: str, task_id: str, **values: Any) -> None:
        self.conn.execute(
            "INSERT INTO execution_attempts(run_id, phase_id, attempt, executor, task_id, process_id, exit_code, started_at, finished_at, summary_path, log_path, user_action_required, suspected_security_issue) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                phase_id,
                attempt,
                executor,
                task_id,
                values.get("process_id"),
                values.get("exit_code"),
                values.get("started_at") or utc_now(),
                values.get("finished_at"),
                values.get("summary_path"),
                values.get("log_path"),
                int(bool(values.get("user_action_required"))),
                int(bool(values.get("suspected_security_issue"))),
            ),
        )
        self.conn.commit()

    def record_validation(self, result: dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO validation_runs(validation_id, run_id, phase_id, result, checked_at, payload_json) VALUES(?,?,?,?,?,?)",
            (
                result["validation_id"],
                result["run_id"],
                result["phase_id"],
                result["result"],
                result["checked_at"],
                json.dumps(result, ensure_ascii=False),
            ),
        )
        self.conn.commit()

    def table_names(self) -> set[str]:
        rows = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {str(row["name"]) for row in rows}

