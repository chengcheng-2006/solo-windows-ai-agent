from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import ApprovalDecision, ApprovalState, RiskLevel, TaskState, ValidationStatus, WorkerState
from .security import assert_secret_safe, is_secret_ref


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TaskCreate(StrictModel):
    objective: str = Field(min_length=1, max_length=20_000)
    task_type: str = Field(default="general", min_length=1, max_length=100)
    source_channel: str = Field(default="wechat", min_length=1, max_length=100)
    parent_task_id: UUID | None = None
    trace_id: UUID | None = None
    timeout_seconds: int = Field(default=900, ge=1, le=604_800)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=200)
    requested_risk: RiskLevel | None = None
    modality: Literal["text", "image", "audio", "multimodal"] = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def reject_secret_material(self) -> "TaskCreate":
        assert_secret_safe({"objective": self.objective, "metadata": self.metadata})
        if "group" in self.source_channel.lower():
            raise ValueError("group sources are disabled")
        return self


class TaskView(StrictModel):
    task_id: UUID
    trace_id: UUID
    parent_task_id: UUID | None
    requester: str
    source_channel: str
    task_type: str
    intent: str
    risk_level: RiskLevel
    risk_reasons: list[str]
    selected_model: str
    selected_executor: str
    current_state: TaskState
    approval_state: ApprovalState
    retry_count: int
    timeout_seconds: int
    created_at: datetime
    updated_at: datetime
    result_artifacts: list[dict[str, Any]]
    validation_result: dict[str, Any]
    redacted_audit_record: dict[str, Any]
    error_code: str | None = None


class StateTransitionRequest(StrictModel):
    to_state: TaskState
    reason_code: str = Field(min_length=1, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def safe(self) -> "StateTransitionRequest":
        assert_secret_safe(self.metadata)
        return self


class CanonicalAction(StrictModel):
    capability: str = Field(min_length=1, max_length=200)
    command: str = Field(min_length=1, max_length=2000)
    cwd: str = Field(min_length=1, max_length=2000)
    arguments: list[str] = Field(default_factory=list, max_length=256)
    file_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def safe(self) -> "CanonicalAction":
        assert_secret_safe(self.model_dump(mode="json"))
        if self.cwd.upper().startswith("E:\\"):
            raise ValueError("E drive is forbidden")
        return self


class ApprovalCreate(StrictModel):
    task_id: UUID
    risk_reason: str = Field(min_length=1, max_length=500)
    action: CanonicalAction
    ttl_seconds: int | None = Field(default=None, ge=30, le=3600)


class ApprovalResolve(StrictModel):
    decision: ApprovalDecision
    action: CanonicalAction


class ApprovalAuthorize(StrictModel):
    action: CanonicalAction


class ApprovalView(StrictModel):
    approval_id: UUID
    task_id: UUID
    requester: str
    risk_level: RiskLevel
    risk_reason: str
    binding_hash: str
    command_hash: str
    file_sha256: str | None
    status: ApprovalState
    expires_at: datetime
    created_at: datetime
    decided_at: datetime | None
    consumed_at: datetime | None


class ArtifactCreate(StrictModel):
    task_id: UUID
    artifact_type: str = Field(min_length=1, max_length=100)
    local_path: str = Field(min_length=1, max_length=2000)
    expected_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    media_type: str | None = Field(default=None, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def safe(self) -> "ArtifactCreate":
        assert_secret_safe(self.metadata)
        if self.local_path.upper().startswith("E:\\"):
            raise ValueError("E drive is forbidden")
        return self


class ArtifactView(StrictModel):
    artifact_id: UUID
    task_id: UUID
    artifact_type: str
    local_path: str
    sha256: str
    size_bytes: int
    media_type: str | None
    metadata: dict[str, Any]
    created_at: datetime


class ValidationRequest(StrictModel):
    task_id: UUID
    status: ValidationStatus
    validator: str = Field(min_length=1, max_length=200)
    checks: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    summary_code: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def safe(self) -> "ValidationRequest":
        assert_secret_safe(self.checks)
        return self


class HealthCheckCreate(StrictModel):
    component: str = Field(min_length=1, max_length=200)
    status: Literal["PASS", "DEGRADED", "FAIL", "UNKNOWN"]
    latency_ms: int | None = Field(default=None, ge=0)
    details: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def safe(self) -> "HealthCheckCreate":
        assert_secret_safe(self.details)
        return self


class ProviderCreate(StrictModel):
    provider_name: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=200)
    executor: str = Field(min_length=1, max_length=100)
    auth_mode: Literal["oauth", "cli_login", "secret_ref", "local", "none"]
    credential_ref: str | None = None
    modalities: list[Literal["text", "image", "audio", "multimodal", "embedding"]]
    context_limit: int = Field(gt=0)
    cost_class: Literal["local", "low", "medium", "high", "subscription"]
    timeout_seconds: int = Field(default=120, ge=1, le=3600)
    rate_limit_per_minute: int | None = Field(default=None, gt=0)
    primary_priority: int = Field(default=100, ge=0, le=10000)
    circuit_breaker_threshold: int = Field(default=3, ge=1, le=20)
    production_enabled: bool = False
    disabled_reason: str | None = Field(default="not_health_verified", max_length=500)

    @model_validator(mode="after")
    def validate_auth(self) -> "ProviderCreate":
        if self.auth_mode == "secret_ref" and not (self.credential_ref and is_secret_ref(self.credential_ref)):
            raise ValueError("secret_ref auth requires a SecretRef")
        if self.auth_mode != "secret_ref" and self.credential_ref is not None:
            raise ValueError("credential_ref is only valid with secret_ref auth")
        if self.production_enabled:
            raise ValueError("providers must pass a health check before production enablement")
        return self


class ProviderHealthCreate(StrictModel):
    status: Literal["HEALTHY", "DEGRADED", "UNHEALTHY", "UNKNOWN"]
    verified_modalities: list[Literal["text", "image", "audio", "multimodal", "embedding"]]
    latency_ms: int | None = Field(default=None, ge=0)
    failure_reason: str | None = Field(default=None, max_length=500)
    enable_if_verified: bool = False


class WorkerCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    worker_type: str = Field(min_length=1, max_length=100)
    state: WorkerState = WorkerState.REGISTERED
    endpoint: str = Field(min_length=1, max_length=500)
    max_concurrency: int = Field(default=1, ge=1, le=64)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("endpoint")
    @classmethod
    def local_endpoint(cls, value: str) -> str:
        allowed = ("pipe://", "http://127.0.0.1:", "http://localhost:", "internal://")
        if not value.startswith(allowed):
            raise ValueError("worker endpoint must be local")
        return value


class CapabilityCreate(StrictModel):
    capability_name: str = Field(min_length=1, max_length=200)
    parameter_schema: dict[str, Any]
    result_schema: dict[str, Any]
    path_policy: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(ge=1, le=86400)
    risk_level: RiskLevel
    requires_approval: bool
    validation_method: str = Field(min_length=1, max_length=200)
    enabled: bool = True

