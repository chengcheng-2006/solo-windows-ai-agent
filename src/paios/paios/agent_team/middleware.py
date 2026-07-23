from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field, SecretStr

from .audit import AuditSink, audit_event
from .errors import AgentTeamError, AuthorizationDenied
from .models import FrozenStrictModel, PlanReviewBundle, ReviewRecord, SubmissionKind, TeamRiskLevel
from .policy import PermissionEnforcer
from .tokens import ApprovalTokenClaims, ApprovalTokenService, TaskTokenClaims, TaskTokenService


class AgentCall(FrozenStrictModel):
    task_id: UUID
    source_agent_id: str = Field(min_length=1, max_length=100)
    target_agent_id: str = Field(min_length=1, max_length=100)
    kind: SubmissionKind
    operation: str = Field(min_length=1, max_length=200)
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_level: TeamRiskLevel = TeamRiskLevel.R0
    side_effect: bool = False
    task_token: SecretStr
    approval_token: SecretStr | None = None
    review: ReviewRecord | PlanReviewBundle | None = None


class AuthorizedCall(FrozenStrictModel):
    task_id: UUID
    source_agent_id: str
    target_agent_id: str
    operation: str
    task_token_id: UUID
    approval_token_id: UUID | None = None


class AgentTeamMiddleware:
    """Integration boundary for every formal inter-agent or worker call."""

    def __init__(
        self,
        policy: PermissionEnforcer,
        task_tokens: TaskTokenService,
        approval_tokens: ApprovalTokenService,
        audit: AuditSink,
    ):
        self.policy = policy
        self.task_tokens = task_tokens
        self.approval_tokens = approval_tokens
        self.audit = audit

    def authorize(self, call: AgentCall) -> AuthorizedCall:
        task_claims: TaskTokenClaims | None = None
        approval_claims: ApprovalTokenClaims | None = None
        try:
            target = self.policy.registry.get(call.target_agent_id)
            token_subject = call.target_agent_id if call.kind == SubmissionKind.DISPATCH and target.is_worker else call.source_agent_id
            task_claims = self.task_tokens.verify(
                call.task_token.get_secret_value(),
                task_id=call.task_id,
                subject=token_subject,
                capability=call.operation,
            )
            self.policy.assert_route(
                source_agent_id=call.source_agent_id,
                target_agent_id=call.target_agent_id,
                kind=call.kind,
                task_id=call.task_id,
                review=call.review,
            )
            operation_actor = call.target_agent_id if call.kind == SubmissionKind.DISPATCH else call.source_agent_id
            self.policy.assert_tool(
                actor_agent_id=operation_actor,
                operation=call.operation,
                parameters=call.parameters,
                risk_level=call.risk_level,
                task_id=call.task_id,
            )
            if call.side_effect and call.risk_level in {TeamRiskLevel.R2, TeamRiskLevel.R3}:
                if call.approval_token is None:
                    raise AuthorizationDenied("approval_token_required", "R2/R3 side effect requires an approval token")
                approval_claims = self.approval_tokens.authorize_once(
                    call.approval_token.get_secret_value(),
                    task_id=call.task_id,
                    action=call.operation,
                    parameters=call.parameters,
                    minimum_risk=call.risk_level,
                )
        except AgentTeamError as exc:
            # Policy denials already have a detailed event; this boundary event ties rejection to the call.
            self.audit.record(
                audit_event(
                    actor_id=call.source_agent_id,
                    event_type="security.agent_call_denied",
                    outcome="DENIED",
                    reason_code=exc.code,
                    task_id=call.task_id,
                    payload={
                        "target_agent_id": call.target_agent_id,
                        "kind": call.kind.value,
                        "operation": call.operation,
                    },
                )
            )
            raise

        assert task_claims is not None
        self.audit.record(
            audit_event(
                actor_id=call.source_agent_id,
                event_type="agent.call_authorized",
                outcome="ALLOWED",
                reason_code="agent_call_authorized",
                task_id=call.task_id,
                payload={
                    "target_agent_id": call.target_agent_id,
                    "kind": call.kind.value,
                    "operation": call.operation,
                    "task_token_id": str(task_claims.token_id),
                    "approval_token_id": str(approval_claims.token_id) if approval_claims else None,
                },
            )
        )
        return AuthorizedCall(
            task_id=call.task_id,
            source_agent_id=call.source_agent_id,
            target_agent_id=call.target_agent_id,
            operation=call.operation,
            task_token_id=task_claims.token_id,
            approval_token_id=approval_claims.token_id if approval_claims else None,
        )
