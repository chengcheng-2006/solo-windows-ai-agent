from __future__ import annotations


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "CREATED": {"PREFLIGHT", "CANCELLED"},
    "PREFLIGHT": {"READY", "WAITING_FOR_USER", "FAILED", "CANCELLED"},
    "READY": {"DISPATCHING", "PAUSED", "CANCELLED"},
    "DISPATCHING": {"RUNNING", "WAITING_FOR_USER", "FAILED", "CANCELLED"},
    "RUNNING": {"WAITING_FOR_COMPLETION", "WAITING_FOR_USER", "PAUSED", "FAILED", "CANCELLED"},
    "WAITING_FOR_COMPLETION": {"VALIDATING", "WAITING_FOR_USER", "FAILED", "CANCELLED"},
    "VALIDATING": {"COMPLETED", "RETRY_PLANNING", "FAILED", "WAITING_FOR_USER", "ROLLING_BACK"},
    "RETRY_PLANNING": {"RETRYING", "FAILED", "WAITING_FOR_USER"},
    "RETRYING": {"RUNNING", "FAILED", "WAITING_FOR_USER"},
    "WAITING_FOR_USER": {"READY", "DISPATCHING", "PAUSED", "CANCELLED", "FAILED"},
    "ROLLING_BACK": {"FAILED", "CANCELLED"},
    "PAUSED": {"READY", "RUNNING", "CANCELLED"},
    "COMPLETED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}


def can_transition(current: str, desired: str) -> bool:
    return desired in ALLOWED_TRANSITIONS.get(current, set())


def require_transition(current: str, desired: str) -> None:
    if not can_transition(current, desired):
        raise ValueError(f"Illegal workflow state transition: {current} -> {desired}")

