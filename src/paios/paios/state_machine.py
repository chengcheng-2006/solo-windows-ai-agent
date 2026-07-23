from __future__ import annotations

from .enums import TaskState


TERMINAL_STATES = {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}

ALLOWED_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.RECEIVED: {TaskState.CLASSIFIED, TaskState.CANCELLED, TaskState.FAILED},
    TaskState.CLASSIFIED: {
        TaskState.WAITING_APPROVAL,
        TaskState.PLANNING,
        TaskState.QUEUED,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.WAITING_APPROVAL: {TaskState.PLANNING, TaskState.QUEUED, TaskState.CANCELLED, TaskState.FAILED},
    TaskState.PLANNING: {TaskState.QUEUED, TaskState.PAUSED, TaskState.RETRYING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.QUEUED: {TaskState.RUNNING, TaskState.PAUSED, TaskState.RETRYING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.RUNNING: {
        TaskState.VALIDATING,
        TaskState.PAUSED,
        TaskState.RETRYING,
        TaskState.RECOVERING,
        TaskState.FAILED,
        TaskState.CANCELLED,
    },
    TaskState.VALIDATING: {TaskState.COMPLETED, TaskState.RETRYING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.RETRYING: {TaskState.QUEUED, TaskState.RUNNING, TaskState.RECOVERING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.PAUSED: {TaskState.QUEUED, TaskState.RUNNING, TaskState.RECOVERING, TaskState.CANCELLED},
    TaskState.RECOVERING: {TaskState.QUEUED, TaskState.RUNNING, TaskState.RETRYING, TaskState.FAILED, TaskState.CANCELLED},
    TaskState.COMPLETED: set(),
    TaskState.FAILED: set(),
    TaskState.CANCELLED: set(),
}


class InvalidTransition(ValueError):
    pass


def assert_transition(current: TaskState, target: TaskState) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(f"invalid task transition: {current} -> {target}")

