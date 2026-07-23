from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


WORKFLOW_STATES = {
    "CREATED",
    "PREFLIGHT",
    "READY",
    "DISPATCHING",
    "RUNNING",
    "WAITING_FOR_COMPLETION",
    "VALIDATING",
    "RETRY_PLANNING",
    "RETRYING",
    "WAITING_FOR_USER",
    "ROLLING_BACK",
    "PAUSED",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
}

PHASE_RESULTS = {
    "PASS",
    "CONDITIONAL_PASS",
    "FAIL",
    "BLOCKED",
    "WAITING_FOR_USER",
    "ROLLED_BACK",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ValidationResult:
    workflow_id: str
    run_id: str
    phase_id: str
    validation_id: str
    result: str
    checks_total: int
    checks_passed: int
    checks_failed: int
    critical_failures: list[str] = field(default_factory=list)
    security_findings: list[str] = field(default_factory=list)
    missing_artifacts: list[str] = field(default_factory=list)
    retryable_findings: list[str] = field(default_factory=list)
    requires_user_action: bool = False
    recommended_next_state: str = "FAILED"
    evidence: list[str] = field(default_factory=list)
    checked_at: str = field(default_factory=utc_now)
    schema_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "run_id": self.run_id,
            "phase_id": self.phase_id,
            "validation_id": self.validation_id,
            "result": self.result,
            "checked_at": self.checked_at,
            "checks_total": self.checks_total,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "critical_failures": self.critical_failures,
            "security_findings": self.security_findings,
            "missing_artifacts": self.missing_artifacts,
            "retryable_findings": self.retryable_findings,
            "requires_user_action": self.requires_user_action,
            "recommended_next_state": self.recommended_next_state,
            "evidence": self.evidence,
        }

