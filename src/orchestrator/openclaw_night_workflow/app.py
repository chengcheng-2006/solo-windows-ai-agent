from __future__ import annotations

from pathlib import Path

from .config import Settings, ensure_directories, get_settings
from .locks import acquire_lock, release_lock
from .manifest import load_manifest
from .task_store import TaskStore


class NightWorkflowOrchestrator:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        ensure_directories(self.settings)
        self.store = TaskStore(self.settings.db_path)
        self.store.migrate()
        self.manifest = load_manifest(self.settings.manifest_path)

    def close(self) -> None:
        self.store.close()

    def health(self) -> dict[str, object]:
        expected = {
            "workflow_runs",
            "phase_runs",
            "workflow_events",
            "execution_attempts",
            "validation_runs",
            "approvals",
            "artifacts",
            "notifications",
            "locks",
            "health_snapshots",
            "rollback_events",
        }
        tables = self.store.table_names()
        return {
            "status": "PASS" if expected <= tables else "FAIL",
            "db_path": str(self.settings.db_path),
            "manifest": self.manifest["workflow_id"],
            "missing_tables": sorted(expected - tables),
        }

    def create_run(self, idempotency_key: str) -> str:
        return self.store.create_workflow_run(self.manifest["workflow_id"], idempotency_key)

    def start_registered_workflow(self, idempotency_key: str, allow_real_phase_start: bool = False) -> dict[str, str]:
        run_id = self.create_run(idempotency_key)
        if not allow_real_phase_start:
            self.store.transition_run(run_id, "PREFLIGHT", payload={"real_phase_start": False})
            self.store.transition_run(run_id, "WAITING_FOR_USER", payload={"reason": "real Phase 1 start requires explicit owner command"})
            return {"run_id": run_id, "state": "WAITING_FOR_USER"}
        raise RuntimeError("Formal Phase 1 execution is disabled in Phase 0 bootstrap.")

    def query_run(self, run_id: str) -> dict[str, str | None]:
        row = self.store.get_run(run_id)
        return {
            "run_id": str(row["run_id"]),
            "workflow_id": str(row["workflow_id"]),
            "state": str(row["state"]),
            "current_phase_id": row["current_phase_id"],
            "updated_at": str(row["updated_at"]),
        }

    def pause_run(self, run_id: str) -> dict[str, str]:
        self.store.transition_run(run_id, "PAUSED", payload={"command": "pause"})
        return {"run_id": run_id, "state": "PAUSED"}

    def resume_run(self, run_id: str) -> dict[str, str]:
        row = self.store.get_run(run_id)
        if row["state"] == "WAITING_FOR_USER":
            self.store.transition_run(run_id, "READY", payload={"command": "resume"})
        else:
            self.store.transition_run(run_id, "READY", payload={"command": "resume"})
        return {"run_id": run_id, "state": "READY"}

    def cancel_run(self, run_id: str) -> dict[str, str]:
        self.store.transition_run(run_id, "CANCELLED", payload={"command": "cancel"})
        return {"run_id": run_id, "state": "CANCELLED"}

    def acquire_singleton(self, owner: str) -> bool:
        return acquire_lock(self.store, "openclaw-night-workflow-singleton", owner)

    def release_singleton(self, owner: str) -> bool:
        return release_lock(self.store, "openclaw-night-workflow-singleton", owner)
