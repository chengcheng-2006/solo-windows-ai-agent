"""Enums for Solo v0.1.1 — task states, risk levels, approval states, deployment modes."""
from __future__ import annotations

from enum import Enum


class TaskState(str, Enum):
    """Workflow task states — aligned with 三省六部 approval pipeline."""

    RECEIVED = "RECEIVED"
    TRIAGED = "TRIAGED"
    PLANNING = "PLANNING"
    REVIEW_PENDING = "REVIEW_PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DISPATCHED = "DISPATCHED"
    EXECUTING = "EXECUTING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"


class RiskLevel(str, Enum):
    """Risk classification levels — matching PAIOS risk taxonomy."""

    R0 = "R0"  # Read-only, no side effects
    R1 = "R1"  # Read with minimal side effects
    R2 = "R2"  # Write with moderate risk, requires approval
    R3 = "R3"  # High risk or irreversible, requires step-level approval


class ApprovalState(str, Enum):
    """Approval lifecycle states."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class ApprovalDecision(str, Enum):
    """Reviewer decision values."""

    APPROVE = "approve"
    REJECT = "reject"


class ValidationStatus(str, Enum):
    """Validation result status."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class DeploymentMode(str, Enum):
    """Solo deployment tiers — progressive capability levels."""

    LITE = "lite"  # Pure Python, zero external deps
    CORE = "core"  # Lite + HTTP + browser
    FULL = "full"  # Core + Docker + GPU
