from __future__ import annotations

from fnmatch import fnmatchcase
from threading import RLock

from .audit import AuditSink, audit_event
from .errors import AuthorizationDenied, RegistryViolation
from .models import CapabilityDefinition, Department, RISK_ORDER, TeamRiskLevel
from .registry import AgentRegistry


def _tool_matches(tool: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatchcase(tool, pattern) for pattern in patterns)


class CapabilityRegistry:
    """Reviewed capability catalog; runtime expansion is owner-only."""

    def __init__(
        self,
        registry: AgentRegistry,
        audit: AuditSink,
        definitions: tuple[CapabilityDefinition, ...] = (),
    ):
        self.registry = registry
        self.audit = audit
        self._definitions: dict[str, CapabilityDefinition] = {}
        self._lock = RLock()
        for definition in definitions:
            self._validate_definition(definition)
            if definition.capability_id in self._definitions:
                raise RegistryViolation("capability_duplicate", "capability_id must be unique")
            self._definitions[definition.capability_id] = definition

    def register_runtime(self, actor_id: str, definition: CapabilityDefinition) -> None:
        for target_agent_id in definition.allowed_agent_ids:
            self.registry.assert_permission_change_authority(
                actor_id,
                target_agent_id,
                self.audit,
                self.registry.document.owner_actor_id,
            )
        self._validate_definition(definition)
        with self._lock:
            if definition.capability_id in self._definitions:
                raise RegistryViolation("capability_duplicate", "capability_id already exists")
            self._definitions[definition.capability_id] = definition
        self.audit.record(
            audit_event(
                actor_id=actor_id,
                event_type="registry.capability_added",
                outcome="ALLOWED",
                reason_code="owner_capability_registration",
                payload={"capability_id": definition.capability_id},
            )
        )

    def resolve(
        self,
        *,
        agent_id: str,
        capability_id: str,
        requested_risk: TeamRiskLevel,
    ) -> CapabilityDefinition:
        agent = self.registry.get(agent_id)
        with self._lock:
            definition = self._definitions.get(capability_id)
        if definition is None or not definition.enabled:
            raise AuthorizationDenied("capability_unavailable", "capability is unavailable")
        if agent_id not in definition.allowed_agent_ids:
            raise AuthorizationDenied("capability_agent_forbidden", "capability is not assigned to this agent")
        if RISK_ORDER[requested_risk] > RISK_ORDER[definition.risk_level]:
            raise AuthorizationDenied("capability_risk_scope_exceeded", "requested risk exceeds capability scope")
        if RISK_ORDER[requested_risk] > RISK_ORDER[agent.risk_ceiling]:
            raise AuthorizationDenied("agent_risk_ceiling_exceeded", "requested risk exceeds agent ceiling")
        return definition

    def all(self) -> tuple[CapabilityDefinition, ...]:
        with self._lock:
            return tuple(self._definitions.values())

    def _validate_definition(self, definition: CapabilityDefinition) -> None:
        for agent_id in definition.allowed_agent_ids:
            agent = self.registry.get(agent_id)
            if _tool_matches(definition.tool, agent.forbidden_tools):
                raise RegistryViolation("capability_uses_forbidden_tool", "capability uses an explicitly forbidden tool")
            if not _tool_matches(definition.tool, agent.allowed_tools):
                raise RegistryViolation("capability_tool_not_allowlisted", "capability tool is not allowlisted")
            if RISK_ORDER[definition.risk_level] > RISK_ORDER[agent.risk_ceiling]:
                raise RegistryViolation("capability_exceeds_agent_risk", "capability exceeds agent risk ceiling")
            if agent.department in {Department.VISION, Department.SPEECH}:
                if _tool_matches(definition.tool, ("shell.*", "powershell.*", "cmd.*", "process.spawn*")):
                    raise RegistryViolation("observation_worker_shell_forbidden", "vision and speech capabilities cannot use shell")
