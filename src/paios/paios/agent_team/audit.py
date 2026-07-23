from __future__ import annotations

from threading import RLock
from typing import Any, Protocol
from uuid import UUID

from ..security import redact
from .models import AuditEvent, FormalTaskState


class AuditSink(Protocol):
    def record(self, event: AuditEvent) -> None: ...


class InMemoryAuditSink:
    """Thread-safe sink for tests and for an integration adapter to drain."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = RLock()

    def record(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.append(event)

    def events(self, task_id: UUID | None = None) -> tuple[AuditEvent, ...]:
        with self._lock:
            if task_id is None:
                return tuple(self._events)
            return tuple(event for event in self._events if event.task_id == task_id)


def audit_event(
    *,
    actor_id: str,
    event_type: str,
    outcome: str,
    reason_code: str,
    task_id: UUID | None = None,
    from_state: FormalTaskState | None = None,
    to_state: FormalTaskState | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    return AuditEvent(
        actor_id=actor_id,
        event_type=event_type,
        outcome=outcome,
        reason_code=reason_code,
        task_id=task_id,
        from_state=from_state,
        to_state=to_state,
        payload=redact(payload or {}),
    )
