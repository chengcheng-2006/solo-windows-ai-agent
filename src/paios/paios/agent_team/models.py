from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import PureWindowsPath
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..security import assert_secret_safe


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FrozenStrictModel(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class Department(StrEnum):
    TAIZI = "taizi"
    ZHONGSHU = "zhongshu"
    MENXIA = "menxia"
    SHANGSHU = "shangshu"
    LIBU = "libu"
    HUBU = "hubu"
    RITES = "rites"
    BINGBU = "bingbu"
    XINGBU = "xingbu"
    GONGBU = "gongbu"
    VISION = "vision"
    SPEECH = "speech"


SIX_MINISTRIES = frozenset(
    {
        Department.LIBU,
        Department.HUBU,
        Department.RITES,
        Department.BINGBU,
        Department.XINGBU,
        Department.GONGBU,
    }
)
WORKER_DEPARTMENTS = SIX_MINISTRIES | {Department.VISION, Department.SPEECH}


class TeamRiskLevel(StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"


RISK_ORDER: dict[TeamRiskLevel, int] = {
    TeamRiskLevel.R0: 0,
    TeamRiskLevel.R1: 1,
    TeamRiskLevel.R2: 2,
    TeamRiskLevel.R3: 3,
}


class HealthState(StrEnum):
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    OFFLINE = "OFFLINE"


class FormalTaskState(StrEnum):
    RECEIVED = "RECEIVED"
    TRIAGED = "TRIAGED"
    PLANNING = "PLANNING"
    REVIEW_PENDING = "REVIEW_PENDING"
    APPROVED = "APPROVED"
    DISPATCHED = "DISPATCHED"
    EXECUTING = "EXECUTING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    VETOED = "VETOED"
    WAITING_USER_APPROVAL = "WAITING_USER_APPROVAL"
    PAUSED = "PAUSED"
    BLOCKED = "BLOCKED"
    RETRYING = "RETRYING"
    RECOVERING = "RECOVERING"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ReviewDecision(StrEnum):
    APPROVED = "APPROVED"
    VETOED = "VETOED"
    APPROVED_WITH_CONDITIONS = "APPROVED_WITH_CONDITIONS"
    HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"


class ReviewStage(StrEnum):
    PLAN = "PLAN"
    FINAL = "FINAL"


class SubmissionKind(StrEnum):
    TASK_INTAKE = "TASK_INTAKE"
    PLAN_REVIEW = "PLAN_REVIEW"
    VETO_RETURN = "VETO_RETURN"
    APPROVED_PLAN = "APPROVED_PLAN"
    DISPATCH = "DISPATCH"
    WORKER_RESULT = "WORKER_RESULT"
    FINAL_REVIEW = "FINAL_REVIEW"
    FINAL_DECISION = "FINAL_DECISION"


class ApprovalAuthority(StrEnum):
    HUMAN = "HUMAN"
    AGENT = "AGENT"


class HeartbeatPolicy(FrozenStrictModel):
    interval_seconds: int = Field(ge=5, le=3600)
    stale_after_seconds: int = Field(ge=10, le=7200)
    offline_after_seconds: int = Field(ge=20, le=86_400)

    @model_validator(mode="after")
    def ordered_thresholds(self) -> "HeartbeatPolicy":
        if self.stale_after_seconds <= self.interval_seconds:
            raise ValueError("stale_after_seconds must exceed interval_seconds")
        if self.offline_after_seconds <= self.stale_after_seconds:
            raise ValueError("offline_after_seconds must exceed stale_after_seconds")
        return self


class AgentDefinition(FrozenStrictModel):
    agent_id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    display_name: str = Field(min_length=1, max_length=100)
    department: Department
    role: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    responsibilities: tuple[str, ...] = Field(min_length=1)
    allowed_inputs: tuple[str, ...] = Field(min_length=1)
    allowed_outputs: tuple[str, ...] = Field(min_length=1)
    allowed_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    default_model: str = Field(min_length=1, max_length=200)
    fallback_models: tuple[str, ...] = ()
    workspace: str = Field(min_length=3, max_length=500)
    max_concurrency: int = Field(ge=1, le=64)
    timeout: int = Field(ge=1, le=86_400)
    risk_ceiling: TeamRiskLevel
    approval_requirement: str = Field(min_length=1, max_length=200)
    heartbeat: HeartbeatPolicy
    health_state: HealthState = HealthState.UNKNOWN
    is_worker: bool = False

    @field_validator("workspace")
    @classmethod
    def workspace_on_project_d_drive(cls, value: str) -> str:
        path = PureWindowsPath(value)
        normalized = str(path).lower()
        required = "d:\\openclaw-hermes-integration\\agents\\"
        if path.drive.upper() != "D:" or not normalized.startswith(required):
            raise ValueError("agent workspace must be under the project agents directory on D drive")
        return str(path)

    @model_validator(mode="after")
    def coherent_permissions(self) -> "AgentDefinition":
        overlap = set(self.allowed_tools) & set(self.forbidden_tools)
        if overlap:
            raise ValueError(f"tools cannot be both allowed and forbidden: {sorted(overlap)}")
        if self.department in WORKER_DEPARTMENTS and not self.is_worker:
            raise ValueError("six-ministry, vision, and speech agents must be workers")
        if self.department not in WORKER_DEPARTMENTS and self.is_worker:
            raise ValueError("coordination agents cannot be declared as workers")
        return self


class AgentMappingDocument(FrozenStrictModel):
    schema_version: str = Field(pattern=r"^paios\.agent-team\.v[0-9]+$")
    architecture_version: str = Field(min_length=1, max_length=100)
    owner_actor_id: str = Field(min_length=1, max_length=100)
    agents: tuple[AgentDefinition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_agents_and_roles(self) -> "AgentMappingDocument":
        ids = [item.agent_id for item in self.agents]
        if len(ids) != len(set(ids)):
            raise ValueError("agent_id values must be unique")
        required_roles = {
            (Department.ZHONGSHU, "chief_planner"),
            (Department.ZHONGSHU, "research_planner"),
            (Department.ZHONGSHU, "technical_planner"),
            (Department.MENXIA, "plan_reviewer"),
            (Department.MENXIA, "security_reviewer"),
            (Department.MENXIA, "resource_reviewer"),
            (Department.MENXIA, "result_validator"),
        }
        present = {(item.department, item.role) for item in self.agents}
        missing = required_roles - present
        if missing:
            raise ValueError(f"required independent roles are missing: {sorted(missing)}")
        return self


class ReviewRecord(FrozenStrictModel):
    review_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    stage: ReviewStage
    plan_revision: int = Field(ge=1)
    reviewer_agent_id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    reviewer_role: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    decision: ReviewDecision
    reasons: tuple[str, ...] = ()
    missing_items: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    rework_requirements: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    reviewed_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def decision_has_required_evidence(self) -> "ReviewRecord":
        assert_secret_safe(self.model_dump(mode="json"))
        if self.decision == ReviewDecision.VETOED:
            if not self.reasons or not self.rework_requirements:
                raise ValueError("VETOED requires reasons and rework_requirements")
            if not (self.missing_items or self.risks):
                raise ValueError("VETOED requires missing_items or risks")
        if self.decision == ReviewDecision.APPROVED_WITH_CONDITIONS and not self.conditions:
            raise ValueError("APPROVED_WITH_CONDITIONS requires conditions")
        if self.decision == ReviewDecision.HUMAN_APPROVAL_REQUIRED and not self.reasons:
            raise ValueError("HUMAN_APPROVAL_REQUIRED requires reasons")
        if self.stage == ReviewStage.FINAL and self.decision == ReviewDecision.APPROVED:
            if not self.evidence_refs:
                raise ValueError("final approval requires evidence_refs")
        return self


class PlanReviewBundle(FrozenStrictModel):
    bundle_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    plan_revision: int = Field(ge=1)
    lead_reviewer_agent_id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,63}$")
    decision: ReviewDecision
    reviews: tuple[ReviewRecord, ...] = Field(min_length=3)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def independent_reviews_are_coherent(self) -> "PlanReviewBundle":
        required_roles = {"plan_reviewer", "security_reviewer", "resource_reviewer"}
        roles = {review.reviewer_role for review in self.reviews}
        if not required_roles.issubset(roles):
            raise ValueError("plan review bundle requires plan, security, and resource reviewers")
        reviewer_ids = [review.reviewer_agent_id for review in self.reviews]
        if len(reviewer_ids) != len(set(reviewer_ids)):
            raise ValueError("plan review bundle reviewers must be independent agents")
        if self.lead_reviewer_agent_id not in reviewer_ids:
            raise ValueError("lead reviewer must be included in reviews")
        lead = next(review for review in self.reviews if review.reviewer_agent_id == self.lead_reviewer_agent_id)
        if lead.reviewer_role != "plan_reviewer":
            raise ValueError("lead reviewer must hold the plan_reviewer role")
        if any(
            review.task_id != self.task_id
            or review.stage != ReviewStage.PLAN
            or review.plan_revision != self.plan_revision
            for review in self.reviews
        ):
            raise ValueError("all plan reviews must bind to the same task and revision")
        decisions = {review.decision for review in self.reviews}
        if ReviewDecision.VETOED in decisions and self.decision != ReviewDecision.VETOED:
            raise ValueError("any reviewer veto forces an overall VETOED decision")
        if ReviewDecision.VETOED not in decisions and ReviewDecision.HUMAN_APPROVAL_REQUIRED in decisions:
            if self.decision != ReviewDecision.HUMAN_APPROVAL_REQUIRED:
                raise ValueError("human approval requirement cannot be downgraded")
        if self.decision == ReviewDecision.APPROVED and decisions != {ReviewDecision.APPROVED}:
            raise ValueError("unconditional approval requires unanimous unconditional reviews")
        if self.decision == ReviewDecision.APPROVED_WITH_CONDITIONS:
            if decisions & {ReviewDecision.VETOED, ReviewDecision.HUMAN_APPROVAL_REQUIRED}:
                raise ValueError("conditional approval cannot override veto or human approval")
            if ReviewDecision.APPROVED_WITH_CONDITIONS not in decisions:
                raise ValueError("conditional approval requires at least one conditional review")
        return self


class FormalTask(FrozenStrictModel):
    task_id: UUID
    current_state: FormalTaskState = FormalTaskState.RECEIVED
    plan_revision: int = Field(default=1, ge=1)
    state_version: int = Field(default=0, ge=0)
    approved_plan_review_id: UUID | None = None
    final_review_id: UUID | None = None
    interrupted_from: FormalTaskState | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Memorial(FrozenStrictModel):
    memorial_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    task_state: FormalTaskState
    plan_revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=300)
    summary: str = Field(min_length=1, max_length=20_000)
    final_review_id: UUID
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    artifact_refs: tuple[str, ...] = ()
    audit_event_ids: tuple[UUID, ...] = Field(min_length=1)
    known_limitations: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def completed_only(self) -> "Memorial":
        assert_secret_safe(self.model_dump(mode="json"))
        if self.task_state != FormalTaskState.COMPLETED:
            raise ValueError("a final memorial requires a COMPLETED task")
        return self


class AuditEvent(FrozenStrictModel):
    event_id: UUID = Field(default_factory=uuid4)
    task_id: UUID | None = None
    actor_id: str = Field(min_length=1, max_length=100)
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,100}$")
    outcome: str = Field(pattern=r"^[A-Z][A-Z0-9_]{1,63}$")
    reason_code: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,120}$")
    from_state: FormalTaskState | None = None
    to_state: FormalTaskState | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def safe_payload(self) -> "AuditEvent":
        assert_secret_safe(self.payload)
        return self


class HeartbeatRecord(FrozenStrictModel):
    agent_id: str
    sequence: int = Field(ge=0)
    observed_at: datetime = Field(default_factory=utc_now)
    health_state: HealthState
    active_task_ids: tuple[UUID, ...] = ()
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def safe_details(self) -> "HeartbeatRecord":
        assert_secret_safe(self.details)
        return self


class CapabilityDefinition(FrozenStrictModel):
    capability_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,100}$")
    display_name: str = Field(min_length=1, max_length=200)
    tool: str = Field(pattern=r"^[a-z][a-z0-9_.*-]{2,120}$")
    allowed_agent_ids: tuple[str, ...] = Field(min_length=1)
    risk_level: TeamRiskLevel
    requires_approval: bool
    side_effect: bool
    parameter_schema: dict[str, Any]
    result_schema: dict[str, Any]
    timeout_seconds: int = Field(ge=1, le=86_400)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    enabled: bool = True

    @model_validator(mode="after")
    def safe_schemas(self) -> "CapabilityDefinition":
        assert_secret_safe({"parameter_schema": self.parameter_schema, "result_schema": self.result_schema})
        if self.risk_level in {TeamRiskLevel.R2, TeamRiskLevel.R3} and self.side_effect:
            if not self.requires_approval:
                raise ValueError("R2/R3 side-effect capabilities require approval")
        return self
