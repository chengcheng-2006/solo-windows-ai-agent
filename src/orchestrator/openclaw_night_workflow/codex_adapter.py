from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from .redaction import redact
from .schemas import utc_now


@dataclass
class DispatchResult:
    task_id: str
    process_id: str | None
    exit_code: int
    summary_path: Path
    log_path: Path
    user_action_required: bool = False
    suspected_security_issue: bool = False


class MockCodexAdapter:
    name = "mock-codex"

    def __init__(self, runtime_dir: Path, logs_dir: Path):
        self.runtime_dir = runtime_dir
        self.logs_dir = logs_dir
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def dispatch(self, run_id: str, phase_id: str, prompt_path: Path, attempt: int = 0) -> DispatchResult:
        task_id = f"mock-{uuid.uuid4().hex[:10]}"
        summary_path = self.runtime_dir / f"{task_id}.summary.json"
        log_path = self.logs_dir / f"{task_id}.log"
        text = prompt_path.read_text(encoding="utf-8", errors="ignore")
        user_action = "[USER ACTION REQUIRED]" in text
        payload = {
            "run_id": run_id,
            "phase_id": phase_id,
            "attempt": attempt,
            "task_id": task_id,
            "exit_code": 0,
            "started_at": utc_now(),
            "finished_at": utc_now(),
            "artifact_paths": [str(summary_path)],
            "user_action_required": user_action,
            "suspected_security_issue": False,
            "note": "Mock executor only; no formal Phase 1/2/3 action executed.",
        }
        summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        log_path.write_text(redact(f"Mock Codex completed {phase_id} for {run_id}\n"), encoding="utf-8")
        return DispatchResult(task_id, None, 0, summary_path, log_path, user_action, False)


class CodexAdapter:
    name = "codex-cli"

    def __init__(self, codex_exe: str | None = None):
        self.codex_exe = codex_exe or shutil.which("codex")

    def health(self) -> dict[str, object]:
        if not self.codex_exe:
            return {"status": "FAIL", "reason": "codex executable not found"}
        version = subprocess.run([self.codex_exe, "--version"], capture_output=True, text=True, timeout=20)
        help_result = subprocess.run([self.codex_exe, "exec", "--help"], capture_output=True, text=True, timeout=20)
        output = redact((version.stdout or version.stderr) + "\n" + (help_result.stdout or help_result.stderr))
        supported = "Run Codex non-interactively" in output or "Usage:" in output
        return {
            "status": "PASS" if version.returncode == 0 and help_result.returncode == 0 and supported else "FAIL",
            "path": self.codex_exe,
            "version_output": redact(version.stdout.strip() or version.stderr.strip()),
            "exec_help_detected": supported,
        }

