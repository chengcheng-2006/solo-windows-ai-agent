from __future__ import annotations

import json
from pathlib import Path

from .audit import AuditSink, audit_event
from .errors import AuthorizationDenied, RegistryViolation
from .models import AgentDefinition, AgentMappingDocument, Department


class AgentRegistry:
    """Immutable runtime view of the reviewed agent mapping."""

    def __init__(self, document: AgentMappingDocument):
        self.document = document
        self._agents = {agent.agent_id: agent for agent in document.agents}

    @classmethod
    def from_file(cls, path: Path) -> "AgentRegistry":
        # The checked-in .yaml is JSON-compatible YAML 1.2, avoiding a runtime YAML dependency.
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RegistryViolation("agent_mapping_unreadable", "agent mapping is not readable") from exc
        try:
            return cls(AgentMappingDocument.model_validate(raw))
        except ValueError as exc:
            raise RegistryViolation("agent_mapping_invalid", "agent mapping failed validation") from exc

    def get(self, agent_id: str) -> AgentDefinition:
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise RegistryViolation("unknown_agent", f"unknown agent_id: {agent_id}") from exc

    def by_department(self, department: Department) -> tuple[AgentDefinition, ...]:
        return tuple(agent for agent in self._agents.values() if agent.department == department)

    def all(self) -> tuple[AgentDefinition, ...]:
        return tuple(self._agents.values())

    def assert_permission_change_authority(
        self,
        actor_id: str,
        target_agent_id: str,
        audit: AuditSink,
        owner_actor_id: str | None = None,
    ) -> None:
        owner = owner_actor_id or self.document.owner_actor_id
        if actor_id == owner:
            self.get(target_agent_id)
            return
        reason = "libu_cannot_expand_permissions" if self.get(actor_id).department == Department.LIBU else "permission_change_requires_owner"
        audit.record(
            audit_event(
                actor_id=actor_id,
                event_type="security.permission_change_denied",
                outcome="DENIED",
                reason_code=reason,
                payload={"target_agent_id": target_agent_id},
            )
        )
        raise AuthorizationDenied(reason, "runtime permission changes require the human owner")
