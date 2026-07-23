from __future__ import annotations

from pathlib import Path

from .schemas import utc_now


class ConsoleNotificationAdapter:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def notify_owner(self, run_id: str, phase_id: str | None, state: str, message: str) -> None:
        self.log_path.write_text(
            f"{utc_now()} owner run_id={run_id} phase_id={phase_id or '-'} state={state} {message}\n",
            encoding="utf-8",
        )

