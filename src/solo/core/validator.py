"""Phase validator — validates task execution results."""
from __future__ import annotations

from .schemas import ValidationResult


def validate_phase(
    workflow_id: str,
    run_id: str,
    phase_id: str,
    validation_id: str,
    *,
    checks_total: int = 0,
    checks_passed: int = 0,
    checks_failed: int = 0,
    critical_failures: list[str] | None = None,
) -> ValidationResult:
    """Create a validation result for a phase.

    This is a simplified constructor that wraps the ValidationResult dataclass.
    In Lite mode, validation is straightforward; in Core/Full mode,
    additional checks (artifact hash, file existence, etc.) are added.
    """
    result = "PASS" if checks_failed == 0 else "FAIL"
    return ValidationResult(
        workflow_id=workflow_id,
        run_id=run_id,
        phase_id=phase_id,
        validation_id=validation_id,
        result=result,
        checks_total=checks_total,
        checks_passed=checks_passed,
        checks_failed=checks_failed,
        critical_failures=critical_failures or [],
    )
