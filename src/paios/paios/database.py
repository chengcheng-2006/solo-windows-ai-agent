from __future__ import annotations

import contextlib
import os
import re
import sqlite3
import threading
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import unquote, urlsplit

from .config import LOOPBACK_HOSTS, ConfigurationError, Settings


PARAM_RE = re.compile(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)")


class CursorLike(Protocol):
    def fetchone(self) -> Mapping[str, Any] | None: ...
    def fetchall(self) -> Sequence[Mapping[str, Any]]: ...


class Database:
    """Small PEP-249 wrapper with named parameters and explicit transactions."""

    def __init__(self, connection: Any, dialect: str):
        self.connection = connection
        self.dialect = dialect
        self._lock = threading.RLock()

    def _adapt(self, sql: str) -> str:
        if self.dialect == "postgresql":
            return PARAM_RE.sub(lambda match: f"%({match.group(1)})s", sql)
        return sql

    def execute(self, sql: str, params: Mapping[str, Any] | None = None) -> CursorLike:
        return self.connection.execute(self._adapt(sql), dict(params or {}))

    @contextlib.contextmanager
    def transaction(self) -> Iterator["Database"]:
        with self._lock:
            try:
                yield self
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise

    def close(self) -> None:
        self.connection.close()

    def ping(self) -> bool:
        with self.transaction():
            row = self.execute("SELECT 1 AS ok").fetchone()
        return bool(row and int(row["ok"]) == 1)


def connect(settings: Settings) -> Database:
    settings.validate()
    parsed = urlsplit(settings.database_url)
    if parsed.scheme == "sqlite":
        if settings.environment != "test":
            raise ConfigurationError("SQLite adapter is test-only")
        return connect_test_sqlite(_sqlite_path(parsed))

    if parsed.scheme not in {"postgresql", "postgres"}:
        raise ConfigurationError("unsupported database scheme")
    if parsed.hostname not in LOOPBACK_HOSTS:
        raise ConfigurationError("PostgreSQL must use a loopback host")
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise ConfigurationError("psycopg is required for the production database") from exc
    connection_options: dict[str, Any] = {"row_factory": dict_row}
    password = os.environ.get("PAIOS_POSTGRES_PASSWORD")
    if password:
        connection_options["password"] = password
    connection = psycopg.connect(settings.database_url, **connection_options)
    return Database(connection, "postgresql")


def connect_test_sqlite(path: Path | str = ":memory:") -> Database:
    """Create the explicit test adapter; never call this from production startup."""

    connection = sqlite3.connect(str(path), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    db = Database(connection, "sqlite-test")
    apply_test_schema(db)
    return db


def _sqlite_path(parsed: Any) -> Path | str:
    if parsed.path in {"", "/:memory:"}:
        return ":memory:"
    value = unquote(parsed.path)
    if re.match(r"^/[A-Za-z]:/", value):
        value = value[1:]
    return Path(value)


def apply_test_schema(db: Database) -> None:
    if db.dialect != "sqlite-test":
        raise ConfigurationError("test schema may only be applied to the test adapter")
    db.connection.executescript(SQLITE_TEST_SCHEMA)
    db.connection.commit()


SQLITE_TEST_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY, applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY, trace_id TEXT NOT NULL, parent_task_id TEXT,
  requester TEXT NOT NULL, source_channel TEXT NOT NULL, task_type TEXT NOT NULL,
  intent TEXT NOT NULL, request_hash TEXT NOT NULL, request_metadata TEXT NOT NULL,
  risk_level TEXT NOT NULL, risk_reasons TEXT NOT NULL,
  selected_model TEXT NOT NULL, selected_executor TEXT NOT NULL,
  routing_decision_id TEXT, current_state TEXT NOT NULL, approval_state TEXT NOT NULL,
  retry_count INTEGER NOT NULL DEFAULT 0, timeout_seconds INTEGER NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, result_artifacts TEXT NOT NULL,
  validation_result TEXT NOT NULL, redacted_audit_record TEXT NOT NULL,
  error_code TEXT, idempotency_key TEXT UNIQUE,
  FOREIGN KEY(parent_task_id) REFERENCES tasks(task_id)
);
CREATE INDEX IF NOT EXISTS ix_tasks_trace_id ON tasks(trace_id);
CREATE INDEX IF NOT EXISTS ix_tasks_state ON tasks(current_state);
CREATE TABLE IF NOT EXISTS task_events (
  event_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, trace_id TEXT NOT NULL,
  event_type TEXT NOT NULL, from_state TEXT, to_state TEXT, payload TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);
CREATE TABLE IF NOT EXISTS event_outbox (
  outbox_id TEXT PRIMARY KEY, event_id TEXT NOT NULL UNIQUE, subject TEXT NOT NULL,
  task_id TEXT, trace_id TEXT, payload TEXT NOT NULL, created_at TEXT NOT NULL,
  published_at TEXT, publish_attempts INTEGER NOT NULL DEFAULT 0, last_error_code TEXT
);
CREATE INDEX IF NOT EXISTS ix_event_outbox_pending ON event_outbox(published_at, created_at);
CREATE TABLE IF NOT EXISTS workflow_runs (
  workflow_run_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, workflow_type TEXT NOT NULL,
  temporal_workflow_id TEXT, temporal_run_id TEXT, status TEXT NOT NULL,
  safe_input_metadata TEXT NOT NULL, started_at TEXT, completed_at TEXT, updated_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);
CREATE TABLE IF NOT EXISTS agents (
  agent_id TEXT PRIMARY KEY, name TEXT NOT NULL, agent_type TEXT NOT NULL,
  status TEXT NOT NULL, capabilities TEXT NOT NULL, last_heartbeat_at TEXT, metadata TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workers (
  worker_id TEXT PRIMARY KEY, name TEXT NOT NULL, worker_type TEXT NOT NULL,
  state TEXT NOT NULL, endpoint TEXT NOT NULL, max_concurrency INTEGER NOT NULL,
  current_load INTEGER NOT NULL DEFAULT 0, registered_at TEXT NOT NULL,
  last_heartbeat_at TEXT, metadata TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS worker_capabilities (
  capability_id TEXT PRIMARY KEY, worker_id TEXT NOT NULL, capability_name TEXT NOT NULL,
  parameter_schema TEXT NOT NULL, result_schema TEXT NOT NULL, path_policy TEXT NOT NULL,
  timeout_seconds INTEGER NOT NULL, risk_level TEXT NOT NULL, requires_approval INTEGER NOT NULL,
  validation_method TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
  UNIQUE(worker_id, capability_name), FOREIGN KEY(worker_id) REFERENCES workers(worker_id)
);
CREATE TABLE IF NOT EXISTS model_providers (
  provider_id TEXT PRIMARY KEY, provider_name TEXT NOT NULL, model_name TEXT NOT NULL,
  executor TEXT NOT NULL, auth_mode TEXT NOT NULL, credential_ref TEXT,
  modalities TEXT NOT NULL, context_limit INTEGER NOT NULL, cost_class TEXT NOT NULL,
  timeout_seconds INTEGER NOT NULL, rate_limit_per_minute INTEGER,
  primary_priority INTEGER NOT NULL, fallback_provider_id TEXT,
  circuit_breaker_threshold INTEGER NOT NULL, production_enabled INTEGER NOT NULL DEFAULT 0,
  disabled_reason TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  UNIQUE(provider_name, model_name)
);
CREATE TABLE IF NOT EXISTS model_health (
  health_id TEXT PRIMARY KEY, provider_id TEXT NOT NULL, status TEXT NOT NULL,
  verified_modalities TEXT NOT NULL, latency_ms INTEGER, failure_reason TEXT,
  consecutive_failures INTEGER NOT NULL DEFAULT 0, circuit_open_until TEXT,
  checked_at TEXT NOT NULL, FOREIGN KEY(provider_id) REFERENCES model_providers(provider_id)
);
CREATE TABLE IF NOT EXISTS routing_decisions (
  decision_id TEXT PRIMARY KEY, task_id TEXT, intent TEXT NOT NULL, modality TEXT NOT NULL,
  selected_provider_id TEXT, selected_model TEXT NOT NULL, selected_executor TEXT NOT NULL,
  fallback_chain TEXT NOT NULL, reason_codes TEXT NOT NULL, candidate_snapshot TEXT NOT NULL,
  created_at TEXT NOT NULL, FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);
CREATE TABLE IF NOT EXISTS approvals (
  approval_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, requester TEXT NOT NULL,
  risk_level TEXT NOT NULL, risk_reason TEXT NOT NULL, canonical_action TEXT NOT NULL,
  binding_hash TEXT NOT NULL, command_hash TEXT NOT NULL, file_sha256 TEXT,
  status TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL,
  decided_at TEXT, consumed_at TEXT, decision_actor TEXT,
  FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);
CREATE INDEX IF NOT EXISTS ix_approvals_task_status ON approvals(task_id, status);
CREATE TABLE IF NOT EXISTS audit_events (
  audit_id TEXT PRIMARY KEY, task_id TEXT, trace_id TEXT, actor TEXT NOT NULL,
  source_channel TEXT NOT NULL, action TEXT NOT NULL, outcome TEXT NOT NULL,
  risk_level TEXT, redacted_metadata TEXT NOT NULL, event_hash TEXT NOT NULL,
  created_at TEXT NOT NULL, FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);
CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, artifact_type TEXT NOT NULL,
  local_path TEXT NOT NULL, sha256 TEXT NOT NULL, size_bytes INTEGER NOT NULL,
  media_type TEXT, metadata TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);
CREATE TABLE IF NOT EXISTS memories (
  memory_id TEXT PRIMARY KEY, owner_scope TEXT NOT NULL, namespace TEXT NOT NULL,
  memory_key TEXT NOT NULL, content TEXT NOT NULL, content_hash TEXT NOT NULL,
  classification TEXT NOT NULL, source_task_id TEXT, expires_at TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(owner_scope, namespace, memory_key)
);
CREATE TABLE IF NOT EXISTS memory_embeddings (
  embedding_id TEXT PRIMARY KEY, memory_id TEXT NOT NULL, embedding_model TEXT NOT NULL,
  dimensions INTEGER NOT NULL, embedding TEXT NOT NULL, created_at TEXT NOT NULL,
  FOREIGN KEY(memory_id) REFERENCES memories(memory_id)
);
CREATE TABLE IF NOT EXISTS secret_access_audits (
  access_id TEXT PRIMARY KEY, task_id TEXT, secret_ref TEXT NOT NULL, purpose TEXT NOT NULL,
  target_process TEXT NOT NULL, allowed INTEGER NOT NULL, outcome TEXT NOT NULL,
  use_count INTEGER NOT NULL, expires_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS health_checks (
  check_id TEXT PRIMARY KEY, component TEXT NOT NULL, status TEXT NOT NULL,
  latency_ms INTEGER, details TEXT NOT NULL, checked_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts (
  alert_id TEXT PRIMARY KEY, dedupe_key TEXT NOT NULL, severity TEXT NOT NULL,
  component TEXT NOT NULL, status TEXT NOT NULL, summary TEXT NOT NULL,
  first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, cooldown_until TEXT,
  recovery_notified_at TEXT, occurrence_count INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS scheduled_jobs (
  job_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, job_type TEXT NOT NULL,
  schedule TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1,
  safe_parameters TEXT NOT NULL, last_run_at TEXT, next_run_at TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
"""
