from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import UUID

from .audit import AuditSink, audit_event
from .errors import RegistryViolation
from .models import HealthState, HeartbeatRecord, utc_now
from .registry import AgentRegistry


class HeartbeatRegistry:
    def __init__(self, registry: AgentRegistry, audit: AuditSink):
        self.registry = registry
        self.audit = audit
        self._records: dict[str, HeartbeatRecord] = {}
        self._lock = RLock()

    def record(
        self,
        *,
        agent_id: str,
        sequence: int,
        reported_state: HealthState,
        active_task_ids: tuple[UUID, ...] = (),
        details: dict[str, Any] | None = None,
        observed_at: datetime | None = None,
    ) -> HeartbeatRecord:
        agent = self.registry.get(agent_id)
        now = observed_at or utc_now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        if reported_state not in {HealthState.HEALTHY, HealthState.DEGRADED}:
            raise RegistryViolation("heartbeat_state_invalid", "agents may report only HEALTHY or DEGRADED")
        if len(active_task_ids) > agent.max_concurrency:
            raise RegistryViolation("heartbeat_concurrency_exceeded", "heartbeat exceeds registered concurrency")
        with self._lock:
            prior = self._records.get(agent_id)
            if prior is not None and sequence <= prior.sequence:
                raise RegistryViolation("heartbeat_replay", "heartbeat sequence must increase")
            record = HeartbeatRecord(
                agent_id=agent_id,
                sequence=sequence,
                observed_at=now,
                health_state=reported_state,
                active_task_ids=active_task_ids,
                details=details or {},
            )
            self._records[agent_id] = record
        self.audit.record(
            audit_event(
                actor_id=agent_id,
                event_type="agent.heartbeat_recorded",
                outcome="ALLOWED",
                reason_code="heartbeat_accepted",
                payload={
                    "sequence": sequence,
                    "health_state": reported_state.value,
                    "active_task_count": len(active_task_ids),
                },
            )
        )
        return record

    def health(self, agent_id: str, now: datetime | None = None) -> HealthState:
        agent = self.registry.get(agent_id)
        current = now or utc_now()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        with self._lock:
            record = self._records.get(agent_id)
        if record is None:
            return HealthState.UNKNOWN
        age = (current - record.observed_at).total_seconds()
        if age >= agent.heartbeat.offline_after_seconds:
            return HealthState.OFFLINE
        if age >= agent.heartbeat.stale_after_seconds:
            return HealthState.STALE
        return record.health_state

    def snapshot(self, now: datetime | None = None) -> dict[str, HealthState]:
        return {agent.agent_id: self.health(agent.agent_id, now) for agent in self.registry.all()}
