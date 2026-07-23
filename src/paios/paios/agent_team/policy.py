from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any
from uuid import UUID

from ..security import SecretMaterialRejected, assert_secret_safe
from .audit import AuditSink, audit_event
from .errors import AuthorizationDenied
from .models import (
    ApprovalAuthority,
    Department,
    PlanReviewBundle,
    ReviewDecision,
    ReviewRecord,
    ReviewStage,
    RISK_ORDER,
    SubmissionKind,
    TeamRiskLevel,
    WORKER_DEPARTMENTS,
)
from .registry import AgentRegistry


ROUTE_RULES = frozenset(
    {
        (Department.TAIZI, Department.ZHONGSHU, SubmissionKind.TASK_INTAKE),
        (Department.ZHONGSHU, Department.MENXIA, SubmissionKind.PLAN_REVIEW),
        (Department.MENXIA, Department.ZHONGSHU, SubmissionKind.VETO_RETURN),
        (Department.MENXIA, Department.SHANGSHU, SubmissionKind.APPROVED_PLAN),
        (Department.SHANGSHU, Department.LIBU, SubmissionKind.DISPATCH),
        (Department.SHANGSHU, Department.HUBU, SubmissionKind.DISPATCH),
        (Department.SHANGSHU, Department.RITES, SubmissionKind.DISPATCH),
        (Department.SHANGSHU, Department.BINGBU, SubmissionKind.DISPATCH),
        (Department.SHANGSHU, Department.XINGBU, SubmissionKind.DISPATCH),
        (Department.SHANGSHU, Department.GONGBU, SubmissionKind.DISPATCH),
        (Department.SHANGSHU, Department.VISION, SubmissionKind.DISPATCH),
        (Department.SHANGSHU, Department.SPEECH, SubmissionKind.DISPATCH),
        (Department.LIBU, Department.SHANGSHU, SubmissionKind.WORKER_RESULT),
        (Department.HUBU, Department.SHANGSHU, SubmissionKind.WORKER_RESULT),
        (Department.RITES, Department.SHANGSHU, SubmissionKind.WORKER_RESULT),
        (Department.BINGBU, Department.SHANGSHU, SubmissionKind.WORKER_RESULT),
        (Department.XINGBU, Department.SHANGSHU, SubmissionKind.WORKER_RESULT),
        (Department.GONGBU, Department.SHANGSHU, SubmissionKind.WORKER_RESULT),
        (Department.VISION, Department.SHANGSHU, SubmissionKind.WORKER_RESULT),
        (Department.SPEECH, Department.SHANGSHU, SubmissionKind.WORKER_RESULT),
        (Department.SHANGSHU, Department.MENXIA, SubmissionKind.FINAL_REVIEW),
        (Department.MENXIA, Department.SHANGSHU, SubmissionKind.FINAL_DECISION),
    }
)


DIRECT_INPUT_PATTERNS = (
    "mouse.*",
    "keyboard.*",
    "pyautogui.*",
    "computer_use.direct*",
    "computer_use.execute*",
)
SHELL_PATTERNS = ("shell.*", "powershell.*", "cmd.*", "process.spawn*")
HIGH_RISK_INPUT_PATTERNS = ("mouse.*", "keyboard.*", "computer_use.*")


def _matches(value: str, patterns: tuple[str, ...] | list[str]) -> bool:
    return any(fnmatchcase(value, pattern) for pattern in patterns)


class PermissionEnforcer:
    """Code-owned mandatory invariants; configuration cannot relax these rules."""

    def __init__(self, registry: AgentRegistry, audit: AuditSink):
        self.registry = registry
        self.audit = audit
        self.owner_actor_id = registry.document.owner_actor_id

    def assert_route(
        self,
        *,
        source_agent_id: str,
        target_agent_id: str,
        kind: SubmissionKind,
        task_id: UUID,
        review: ReviewRecord | PlanReviewBundle | None = None,
    ) -> None:
        source = self.registry.get(source_agent_id)
        target = self.registry.get(target_agent_id)
        if (source.department, target.department, kind) not in ROUTE_RULES:
            self._deny(
                actor_id=source_agent_id,
                task_id=task_id,
                reason="submission_route_forbidden",
                event_type="security.route_denied",
                payload={"target_agent_id": target_agent_id, "kind": kind.value},
            )

        if source.department == Department.TAIZI and target.department != Department.ZHONGSHU:
            self._deny(source_agent_id, task_id, "taizi_must_submit_zhongshu", "security.route_denied")
        if source.department == Department.ZHONGSHU and target.department != Department.MENXIA:
            self._deny(source_agent_id, task_id, "zhongshu_must_submit_menxia", "security.route_denied")
        if source.department in WORKER_DEPARTMENTS and target.department != Department.SHANGSHU:
            self._deny(source_agent_id, task_id, "worker_must_return_shangshu", "security.route_denied")

        if kind == SubmissionKind.APPROVED_PLAN:
            self._assert_review(
                source_agent_id,
                task_id,
                review,
                ReviewStage.PLAN,
                {ReviewDecision.APPROVED, ReviewDecision.APPROVED_WITH_CONDITIONS},
                "approved_plan_requires_menxia_review",
            )
        elif kind == SubmissionKind.VETO_RETURN:
            self._assert_review(
                source_agent_id,
                task_id,
                review,
                ReviewStage.PLAN,
                {ReviewDecision.VETOED},
                "veto_return_requires_veto_review",
            )
        elif kind == SubmissionKind.FINAL_DECISION:
            self._assert_review(
                source_agent_id,
                task_id,
                review,
                ReviewStage.FINAL,
                set(ReviewDecision),
                "final_decision_requires_menxia_review",
            )

    def assert_tool(
        self,
        *,
        actor_agent_id: str,
        operation: str,
        parameters: dict[str, Any],
        risk_level: TeamRiskLevel,
        task_id: UUID,
    ) -> None:
        agent = self.registry.get(actor_agent_id)
        try:
            assert_secret_safe(parameters)
        except SecretMaterialRejected as exc:
            reason = "hubu_plaintext_secret_forbidden" if agent.department == Department.HUBU else "plaintext_secret_forbidden"
            self._deny(
                actor_agent_id,
                task_id,
                reason,
                "security.secret_material_denied",
                {"parameter_keys": sorted(str(key) for key in parameters)},
            )
            raise AssertionError("unreachable") from exc

        if agent.department in {Department.TAIZI, Department.ZHONGSHU} and _matches(operation, DIRECT_INPUT_PATTERNS):
            self._deny(actor_agent_id, task_id, "frontdesk_planner_computer_use_bypass", "security.tool_denied")
        if agent.department in {Department.VISION, Department.SPEECH} and _matches(operation, SHELL_PATTERNS):
            self._deny(actor_agent_id, task_id, "observation_worker_shell_forbidden", "security.tool_denied")
        if _matches(operation, list(agent.forbidden_tools)):
            self._deny(actor_agent_id, task_id, "tool_explicitly_forbidden", "security.tool_denied")
        if not _matches(operation, list(agent.allowed_tools)):
            self._deny(actor_agent_id, task_id, "tool_not_allowlisted", "security.tool_denied")
        if RISK_ORDER[risk_level] > RISK_ORDER[agent.risk_ceiling]:
            self._deny(actor_agent_id, task_id, "agent_risk_ceiling_exceeded", "security.risk_denied")

    def assert_can_approve(
        self,
        actor_id: str,
        risk_level: TeamRiskLevel,
        operation: str,
        authority: ApprovalAuthority,
        task_id: UUID,
    ) -> None:
        if actor_id == self.owner_actor_id:
            if authority != ApprovalAuthority.HUMAN:
                self._deny(actor_id, task_id, "owner_approval_must_be_human", "security.approval_denied")
            return

        agent = self.registry.get(actor_id)
        if authority != ApprovalAuthority.AGENT:
            self._deny(actor_id, task_id, "agent_cannot_claim_human_authority", "security.approval_denied")
        if agent.department == Department.GONGBU and _matches(operation, ("production.deploy*", "deploy.production*")):
            self._deny(actor_id, task_id, "gongbu_cannot_approve_production_deploy", "security.approval_denied")
        if agent.department == Department.BINGBU and RISK_ORDER[risk_level] >= RISK_ORDER[TeamRiskLevel.R2]:
            if _matches(operation, HIGH_RISK_INPUT_PATTERNS):
                self._deny(actor_id, task_id, "bingbu_cannot_approve_high_risk_input", "security.approval_denied")
        if risk_level == TeamRiskLevel.R3:
            reason = "xingbu_cannot_approve_r3" if agent.department == Department.XINGBU else "r3_requires_human_owner"
            self._deny(actor_id, task_id, reason, "security.approval_denied")
        if agent.department not in {Department.MENXIA, Department.XINGBU}:
            self._deny(actor_id, task_id, "agent_not_approval_authority", "security.approval_denied")

    def assert_permission_change(self, actor_id: str, target_agent_id: str) -> None:
        self.registry.assert_permission_change_authority(
            actor_id,
            target_agent_id,
            self.audit,
            self.owner_actor_id,
        )

    def _assert_review(
        self,
        actor_id: str,
        task_id: UUID,
        review: ReviewRecord | PlanReviewBundle | None,
        stage: ReviewStage,
        decisions: set[ReviewDecision],
        reason: str,
    ) -> None:
        if (
            review is None
            or review.task_id != task_id
            or review.decision not in decisions
        ):
            self._deny(actor_id, task_id, reason, "security.review_binding_denied")
        if isinstance(review, PlanReviewBundle):
            if stage != ReviewStage.PLAN or review.lead_reviewer_agent_id != actor_id:
                self._deny(actor_id, task_id, reason, "security.review_binding_denied")
        elif review.stage != stage or review.reviewer_agent_id != actor_id:
            self._deny(actor_id, task_id, reason, "security.review_binding_denied")

    def _deny(
        self,
        actor_id: str,
        task_id: UUID | None,
        reason: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.audit.record(
            audit_event(
                actor_id=actor_id,
                event_type=event_type,
                outcome="DENIED",
                reason_code=reason,
                task_id=task_id,
                payload=payload,
            )
        )
        raise AuthorizationDenied(reason, "agent-team authorization denied")
