"""Data schemas for Solo v0.1.1 — lightweight dataclasses with no Pydantic dependency."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


@dataclass
class ValidationResult:
    """Result of a phase validation check."""
    workflow_id: str
    run_id: str
    phase_id: str
    validation_id: str
    result: str  # PASS | FAIL | BLOCKED
    checks_total: int = 0
    checks_passed: int = 0
    checks_failed: int = 0
    critical_failures: list[str] = field(default_factory=list)
    security_findings: list[str] = field(default_factory=list)
    missing_artifacts: list[str] = field(default_factory=list)
    retryable_findings: list[str] = field(default_factory=list)
    requires_user_action: bool = False
    recommended_next_state: str = ""
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "run_id": self.run_id,
            "phase_id": self.phase_id,
            "validation_id": self.validation_id,
            "result": self.result,
            "checks_total": self.checks_total,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "critical_failures": list(self.critical_failures),
            "security_findings": list(self.security_findings),
            "missing_artifacts": list(self.missing_artifacts),
            "retryable_findings": list(self.retryable_findings),
            "requires_user_action": self.requires_user_action,
            "recommended_next_state": self.recommended_next_state,
            "evidence": list(self.evidence),
        }


@dataclass
class PipelineEvent:
    """A single event in a pipeline run."""
    state: str
    ok: bool
    detail: str = ""
    payload: dict[str, Any] | None = None
