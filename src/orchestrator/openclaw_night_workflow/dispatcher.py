from __future__ import annotations

from pathlib import Path

from .codex_adapter import MockCodexAdapter
from .task_store import TaskStore


class PhaseDispatcher:
    def __init__(self, store: TaskStore, root: Path):
        self.store = store
        self.root = root
        self.adapter = MockCodexAdapter(root / "runtime", root / "logs")

    def dispatch_mock_phase(self, run_id: str, phase: dict, attempt: int = 0):
        prompt_path = self.root / phase["prompt_path"]
        result = self.adapter.dispatch(run_id, phase["phase_id"], prompt_path, attempt)
        self.store.record_execution_attempt(
            run_id,
            phase["phase_id"],
            attempt,
            self.adapter.name,
            result.task_id,
            process_id=result.process_id,
            exit_code=result.exit_code,
            finished_at=None,
            summary_path=str(result.summary_path),
            log_path=str(result.log_path),
            user_action_required=result.user_action_required,
            suspected_security_issue=result.suspected_security_issue,
        )
        return result

