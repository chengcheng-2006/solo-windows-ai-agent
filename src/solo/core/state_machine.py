"""Workflow state machine — ADR 003 8-step pipeline.

All states and transitions are pure Python with no external dependencies.
"""
from __future__ import annotations

# ruff: noqa: N818 — InvalidTransitionError is a ValueError, naming is intentional

# Allowed transitions per ADR 003
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "RECEIVED":       {"TRIAGED", "REJECTED"},
    "TRIAGED":        {"PLANNING", "REVIEW_PENDING", "REJECTED"},
    "PLANNING":       {"DISPATCHED"},
    "REVIEW_PENDING": {"APPROVED", "REJECTED"},
    "APPROVED":       {"DISPATCHED"},
    "REJECTED":       set(),                     # Terminal state
    "DISPATCHED":     {"EXECUTING"},
    "EXECUTING":      {"VALIDATING"},
    "VALIDATING":     {"COMPLETED"},
    "COMPLETED":      set(),                     # Terminal state
}

TERMINAL_STATES: set[str] = {"REJECTED", "COMPLETED"}


class InvalidTransitionError(ValueError):
    """Raised when an illegal state transition is attempted."""


def can_transition(current: str, target: str) -> bool:
    """Check if a transition from current to target is allowed."""
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    return target in allowed


def require_transition(current: str, target: str) -> None:
    """Require a legal transition; raise InvalidTransitionError if not allowed."""
    if not can_transition(current, target):
        raise InvalidTransitionError(
            f"Cannot transition from {current!r} to {target!r}. "
            f"Allowed targets from {current!r}: {sorted(ALLOWED_TRANSITIONS.get(current, set()))}"
        )
