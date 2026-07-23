from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from .config import Settings
from .database import Database
from .enums import ApprovalDecision, ApprovalState, RiskLevel, TaskState, ValidationStatus
from .policy import PolicyEngine
from .risk import RiskClassifier
from .schemas import (
    ApprovalAuthorize,
    ApprovalCreate,
    ApprovalResolve,
    ApprovalView,
    ArtifactCreate,
    ArtifactView,
    CanonicalAction,
    HealthCheckCreate,
    StateTransitionRequest,
    TaskCreate,
    TaskView,
    ValidationRequest,
)
from .security import canonical_json, redact, sha256_file, sha256_text
from .state_machine import assert_transition


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def encode(value: Any) -> str:
    return canonical_json(value)


def decode(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def row_dict(row: Any) -> dict[str, Any]:
    return dict(row)


class NotFoundError(LookupError):
    pass


class ConflictError(RuntimeError):
    pass


class AuthorizationError(RuntimeError):
    pass


class ControlPlane:
    def __init__(self, database: Database, settings: Settings):
        self.database = database
        self.settings = settings
        self.risk = RiskClassifier()
        self.policy = PolicyEngine()

    def create_task(self, request: TaskCreate, requester: str) -> TaskView:
        if request.idempotency_key:
            row = self.database.execute(
                "SELECT * FROM tasks WHERE idempotency_key=:key", {"key": request.idempotency_key}
            ).fetchone()
            if row:
                return self._task_view(row)

        assessment = self.risk.classify(request.objective, request.task_type, request.requested_risk)
        decision = self.policy.evaluate(requester, self.settings.owner_id, request.source_channel, assessment.level)
        if not decision.allowed:
            raise AuthorizationError(decision.reason_code)

        task_id = uuid4()
        trace_id = request.trace_id or uuid4()
        routing_id = uuid4()
        now = utc_now().isoformat()
        intent, model, executor, reasons = self._route(request)
        approval_state = ApprovalState.PENDING if decision.requires_approval else ApprovalState.NOT_REQUIRED
        request_hash = sha256_text(request.objective)
        safe_metadata = {
            "objective_sha256": request_hash,
            "objective_length": len(request.objective),
            "modality": request.modality,
            "metadata": redact(request.metadata),
        }
        audit = {
            "request_hash": request_hash,
            "policy": decision.reason_code,
            "routing_reason_codes": reasons,
        }

        with self.database.transaction():
            self.database.execute(
                """
                INSERT INTO routing_decisions (
                  decision_id, task_id, intent, modality, selected_provider_id,
                  selected_model, selected_executor, fallback_chain, reason_codes,
                  candidate_snapshot, created_at
                ) VALUES (
                  :decision_id, NULL, :intent, :modality, NULL, :model, :executor,
                  :fallback, :reasons, :candidates, :created_at
                )
                """,
                {
                    "decision_id": str(routing_id),
                    "intent": intent,
                    "modality": request.modality,
                    "model": model,
                    "executor": executor,
                    "fallback": encode([]),
                    "reasons": encode(reasons),
                    "candidates": encode([]),
                    "created_at": now,
                },
            )
            self.database.execute(
                """
                INSERT INTO tasks (
                  task_id, trace_id, parent_task_id, requester, source_channel, task_type,
                  intent, request_hash, request_metadata, risk_level, risk_reasons,
                  selected_model, selected_executor, routing_decision_id, current_state,
                  approval_state, retry_count, timeout_seconds, created_at, updated_at,
                  result_artifacts, validation_result, redacted_audit_record, error_code,
                  idempotency_key
                ) VALUES (
                  :task_id, :trace_id, :parent_task_id, :requester, :source_channel,
                  :task_type, :intent, :request_hash, :request_metadata, :risk_level,
                  :risk_reasons, :selected_model, :selected_executor, :routing_id,
                  :current_state, :approval_state, 0, :timeout_seconds, :created_at,
                  :updated_at, :result_artifacts, :validation_result, :audit, NULL,
                  :idempotency_key
                )
                """,
                {
                    "task_id": str(task_id),
                    "trace_id": str(trace_id),
                    "parent_task_id": str(request.parent_task_id) if request.parent_task_id else None,
                    "requester": requester,
                    "source_channel": request.source_channel,
                    "task_type": request.task_type,
                    "intent": intent,
                    "request_hash": request_hash,
                    "request_metadata": encode(safe_metadata),
                    "risk_level": assessment.level.value,
                    "risk_reasons": encode(list(assessment.reasons)),
                    "selected_model": model,
                    "selected_executor": executor,
                    "routing_id": str(routing_id),
                    "current_state": TaskState.RECEIVED.value,
                    "approval_state": approval_state.value,
                    "timeout_seconds": request.timeout_seconds,
                    "created_at": now,
                    "updated_at": now,
                    "result_artifacts": encode([]),
                    "validation_result": encode({"status": ValidationStatus.PENDING.value}),
                    "audit": encode(audit),
                    "idempotency_key": request.idempotency_key,
                },
            )
            self.database.execute(
                "UPDATE routing_decisions SET task_id=:task_id WHERE decision_id=:decision_id",
                {"task_id": str(task_id), "decision_id": str(routing_id)},
            )
            self._event(task_id, trace_id, "task.created", None, TaskState.RECEIVED, safe_metadata)
            self._set_state(task_id, trace_id, TaskState.RECEIVED, TaskState.CLASSIFIED, "intent_classified", {})
            if decision.requires_approval:
                self._set_state(
                    task_id,
                    trace_id,
                    TaskState.CLASSIFIED,
                    TaskState.WAITING_APPROVAL,
                    decision.reason_code,
                    {},
                )
        return self.get_task(task_id)

    def get_task(self, task_id: UUID) -> TaskView:
        row = self.database.execute("SELECT * FROM tasks WHERE task_id=:task_id", {"task_id": str(task_id)}).fetchone()
        if not row:
            raise NotFoundError("task not found")
        return self._task_view(row)

    def list_tasks(self, limit: int = 100) -> list[TaskView]:
        rows = self.database.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT :limit", {"limit": limit}
        ).fetchall()
        return [self._task_view(row) for row in rows]

    def transition(self, task_id: UUID, request: StateTransitionRequest) -> TaskView:
        task = self.get_task(task_id)
        assert_transition(task.current_state, request.to_state)
        with self.database.transaction():
            self._set_state(task_id, task.trace_id, task.current_state, request.to_state, request.reason_code, request.metadata)
        return self.get_task(task_id)

    def create_approval(self, request: ApprovalCreate, requester: str) -> ApprovalView:
        task = self.get_task(request.task_id)
        if task.requester != requester:
            raise AuthorizationError("approval requester mismatch")
        if task.risk_level not in {RiskLevel.R2, RiskLevel.R3}:
            raise ConflictError("approval is only valid for R2 or R3 tasks")
        now = utc_now()
        expires = now + timedelta(seconds=request.ttl_seconds or self.settings.approval_ttl_seconds)
        approval_id = uuid4()
        binding_hash = self._binding_hash(task, request.action)
        with self.database.transaction():
            self.database.execute(
                """
                INSERT INTO approvals (
                  approval_id, task_id, requester, risk_level, risk_reason,
                  canonical_action, binding_hash, command_hash, file_sha256, status,
                  expires_at, created_at, decided_at, consumed_at, decision_actor
                ) VALUES (
                  :approval_id, :task_id, :requester, :risk_level, :risk_reason,
                  :canonical_action, :binding_hash, :command_hash, :file_sha256,
                  :status, :expires_at, :created_at, NULL, NULL, NULL
                )
                """,
                {
                    "approval_id": str(approval_id),
                    "task_id": str(task.task_id),
                    "requester": requester,
                    "risk_level": task.risk_level.value,
                    "risk_reason": request.risk_reason,
                    "canonical_action": encode(request.action.model_dump(mode="json")),
                    "binding_hash": binding_hash,
                    "command_hash": sha256_text(request.action.command),
                    "file_sha256": request.action.file_sha256,
                    "status": ApprovalState.PENDING.value,
                    "expires_at": expires.isoformat(),
                    "created_at": now.isoformat(),
                },
            )
            self._event(task.task_id, task.trace_id, "approval.requested", None, None, {"approval_id": str(approval_id), "binding_hash": binding_hash})
        return self.get_approval(approval_id)

    def get_approval(self, approval_id: UUID) -> ApprovalView:
        row = self.database.execute(
            "SELECT * FROM approvals WHERE approval_id=:approval_id", {"approval_id": str(approval_id)}
        ).fetchone()
        if not row:
            raise NotFoundError("approval not found")
        return self._approval_view(row)

    def resolve_approval(self, approval_id: UUID, request: ApprovalResolve, actor: str) -> ApprovalView:
        approval = self.get_approval(approval_id)
        task = self.get_task(approval.task_id)
        self._assert_approval_pending(approval)
        if self._binding_hash(task, request.action) != approval.binding_hash:
            raise AuthorizationError("approval action binding mismatch")
        state = ApprovalState.APPROVED if request.decision == ApprovalDecision.APPROVE else ApprovalState.DENIED
        now = utc_now().isoformat()
        with self.database.transaction():
            self.database.execute(
                "UPDATE approvals SET status=:status, decided_at=:now, decision_actor=:actor WHERE approval_id=:approval_id",
                {"status": state.value, "now": now, "actor": actor, "approval_id": str(approval_id)},
            )
            self.database.execute(
                "UPDATE tasks SET approval_state=:status, updated_at=:now WHERE task_id=:task_id",
                {"status": state.value, "now": now, "task_id": str(task.task_id)},
            )
            self._event(task.task_id, task.trace_id, "approval.resolved", None, None, {"status": state.value, "binding_hash": approval.binding_hash})
        return self.get_approval(approval_id)

    def authorize_approval(self, approval_id: UUID, request: ApprovalAuthorize) -> ApprovalView:
        approval = self.get_approval(approval_id)
        task = self.get_task(approval.task_id)
        if approval.status != ApprovalState.APPROVED:
            raise AuthorizationError("approval is not approved")
        if approval.expires_at <= utc_now():
            self._expire_approval(approval_id, task.task_id)
            raise AuthorizationError("approval expired")
        if self._binding_hash(task, request.action) != approval.binding_hash:
            raise AuthorizationError("approval action binding mismatch")
        now = utc_now().isoformat()
        with self.database.transaction():
            self.database.execute(
                "UPDATE approvals SET status=:status, consumed_at=:now WHERE approval_id=:approval_id AND status=:approved",
                {
                    "status": ApprovalState.CONSUMED.value,
                    "now": now,
                    "approval_id": str(approval_id),
                    "approved": ApprovalState.APPROVED.value,
                },
            )
            self.database.execute(
                "UPDATE tasks SET approval_state=:status, updated_at=:now WHERE task_id=:task_id",
                {"status": ApprovalState.CONSUMED.value, "now": now, "task_id": str(task.task_id)},
            )
        return self.get_approval(approval_id)

    def add_artifact(self, request: ArtifactCreate) -> ArtifactView:
        task = self.get_task(request.task_id)
        path = Path(request.local_path).resolve(strict=True)
        if not path.is_file() or not any(path.is_relative_to(root.resolve()) for root in self.settings.artifact_roots):
            raise AuthorizationError("artifact path is outside approved roots")
        digest = sha256_file(path)
        if request.expected_sha256 and digest.lower() != request.expected_sha256.lower():
            raise ConflictError("artifact hash mismatch")
        artifact_id = uuid4()
        now = utc_now().isoformat()
        with self.database.transaction():
            self.database.execute(
                """
                INSERT INTO artifacts (
                  artifact_id, task_id, artifact_type, local_path, sha256, size_bytes,
                  media_type, metadata, created_at
                ) VALUES (
                  :artifact_id, :task_id, :artifact_type, :local_path, :sha256,
                  :size_bytes, :media_type, :metadata, :created_at
                )
                """,
                {
                    "artifact_id": str(artifact_id),
                    "task_id": str(task.task_id),
                    "artifact_type": request.artifact_type,
                    "local_path": str(path),
                    "sha256": digest,
                    "size_bytes": path.stat().st_size,
                    "media_type": request.media_type,
                    "metadata": encode(redact(request.metadata)),
                    "created_at": now,
                },
            )
            artifact_summary = list(task.result_artifacts)
            artifact_summary.append({
                "artifact_id": str(artifact_id), "artifact_type": request.artifact_type,
                "local_path": str(path), "sha256": digest, "size_bytes": path.stat().st_size,
                "media_type": request.media_type,
            })
            self.database.execute(
                "UPDATE tasks SET result_artifacts=:artifacts,updated_at=:now WHERE task_id=:task_id",
                {"artifacts": encode(artifact_summary), "now": now, "task_id": str(task.task_id)},
            )
        return self.get_artifact(artifact_id)

    def get_artifact(self, artifact_id: UUID) -> ArtifactView:
        row = self.database.execute(
            "SELECT * FROM artifacts WHERE artifact_id=:artifact_id", {"artifact_id": str(artifact_id)}
        ).fetchone()
        if not row:
            raise NotFoundError("artifact not found")
        data = row_dict(row)
        data["metadata"] = decode(data["metadata"], {})
        return ArtifactView.model_validate(data)

    def validate_result(self, request: ValidationRequest) -> TaskView:
        task = self.get_task(request.task_id)
        result = request.model_dump(mode="json")
        now = utc_now().isoformat()
        with self.database.transaction():
            self.database.execute(
                "UPDATE tasks SET validation_result=:result, updated_at=:now WHERE task_id=:task_id",
                {"result": encode(result), "now": now, "task_id": str(task.task_id)},
            )
        return self.get_task(task.task_id)

    def record_health(self, request: HealthCheckCreate) -> UUID:
        check_id = uuid4()
        with self.database.transaction():
            self.database.execute(
                "INSERT INTO health_checks (check_id, component, status, latency_ms, details, checked_at) VALUES (:id,:component,:status,:latency,:details,:now)",
                {
                    "id": str(check_id),
                    "component": request.component,
                    "status": request.status,
                    "latency": request.latency_ms,
                    "details": encode(redact(request.details)),
                    "now": utc_now().isoformat(),
                },
            )
        return check_id

    def _set_state(
        self,
        task_id: UUID,
        trace_id: UUID,
        current: TaskState,
        target: TaskState,
        reason: str,
        metadata: dict[str, Any],
    ) -> None:
        assert_transition(current, target)
        now = utc_now().isoformat()
        self.database.execute(
            "UPDATE tasks SET current_state=:state, updated_at=:now WHERE task_id=:task_id AND current_state=:current",
            {"state": target.value, "now": now, "task_id": str(task_id), "current": current.value},
        )
        state_events = {
            TaskState.CLASSIFIED: "task.routed",
            TaskState.RUNNING: "task.started",
            TaskState.COMPLETED: "task.completed",
            TaskState.FAILED: "task.failed",
        }
        self._event(
            task_id, trace_id, state_events.get(target, "task.progress"), current, target,
            {"reason_code": reason, "metadata": redact(metadata)},
        )

    def _event(
        self,
        task_id: UUID,
        trace_id: UUID,
        event_type: str,
        current: TaskState | None,
        target: TaskState | None,
        payload: dict[str, Any],
    ) -> None:
        event_id = uuid4()
        created_at = utc_now().isoformat()
        safe_payload = redact(payload)
        event_values = {
            "event_id": str(event_id),
            "task_id": str(task_id),
            "trace_id": str(trace_id),
            "event_type": event_type,
            "from_state": current.value if current else None,
            "to_state": target.value if target else None,
            "payload": encode(safe_payload),
            "key": str(event_id),
            "created_at": created_at,
        }
        self.database.execute(
            """
            INSERT INTO task_events (
              event_id, task_id, trace_id, event_type, from_state, to_state,
              payload, idempotency_key, created_at
            ) VALUES (:event_id,:task_id,:trace_id,:event_type,:from_state,:to_state,:payload,:key,:created_at)
            """,
            event_values,
        )
        self.database.execute(
            """
            INSERT INTO event_outbox (
              outbox_id, event_id, subject, task_id, trace_id, payload,
              created_at, published_at, publish_attempts, last_error_code
            ) VALUES (
              :outbox_id,:event_id,:subject,:task_id,:trace_id,:payload,
              :created_at,NULL,0,NULL
            )
            """,
            {
                "outbox_id": str(uuid4()), "event_id": str(event_id), "subject": event_type,
                "task_id": str(task_id), "trace_id": str(trace_id),
                "payload": encode({
                    "schema": "paios.event.v1", "event_id": str(event_id),
                    "task_id": str(task_id), "trace_id": str(trace_id),
                    "subject": event_type, "from_state": current.value if current else None,
                    "to_state": target.value if target else None, "metadata": safe_payload,
                    "created_at": created_at,
                }),
                "created_at": created_at,
            },
        )

    def _task_view(self, row: Any) -> TaskView:
        data = row_dict(row)
        for field, fallback in (
            ("risk_reasons", []),
            ("result_artifacts", []),
            ("validation_result", {}),
            ("redacted_audit_record", {}),
        ):
            data[field] = decode(data[field], fallback)
        public = {name: data[name] for name in TaskView.model_fields if name in data}
        return TaskView.model_validate(public)

    def _approval_view(self, row: Any) -> ApprovalView:
        data = row_dict(row)
        public = {name: data[name] for name in ApprovalView.model_fields if name in data}
        return ApprovalView.model_validate(public)

    def _binding_hash(self, task: TaskView, action: CanonicalAction) -> str:
        return sha256_text(
            canonical_json(
                {
                    "task_id": str(task.task_id),
                    "requester": task.requester,
                    "risk_level": task.risk_level.value,
                    "action": action.model_dump(mode="json"),
                }
            )
        )

    def _assert_approval_pending(self, approval: ApprovalView) -> None:
        if approval.status != ApprovalState.PENDING:
            raise ConflictError("approval is not pending")
        if approval.expires_at <= utc_now():
            self._expire_approval(approval.approval_id, approval.task_id)
            raise AuthorizationError("approval expired")

    def _expire_approval(self, approval_id: UUID, task_id: UUID) -> None:
        now = utc_now().isoformat()
        with self.database.transaction():
            self.database.execute(
                "UPDATE approvals SET status=:status WHERE approval_id=:approval_id",
                {"status": ApprovalState.EXPIRED.value, "approval_id": str(approval_id)},
            )
            self.database.execute(
                "UPDATE tasks SET approval_state=:status, updated_at=:now WHERE task_id=:task_id",
                {"status": ApprovalState.EXPIRED.value, "now": now, "task_id": str(task_id)},
            )

    @staticmethod
    def _route(request: TaskCreate) -> tuple[str, str, str, list[str]]:
        text = f"{request.task_type} {request.objective}".lower()
        if request.modality in {"image", "multimodal"} or any(term in text for term in ("ocr", "vision", "image")):
            return "vision", "vision-health-routed", "vision-worker", ["vision_modality"]
        if any(term in text for term in ("code", "coding", "deploy", "test repo", "codex")):
            return "engineering", "codex-plus-oauth", "codex-worker", ["engineering_intent"]
        if any(term in text for term in ("browser", "website", "navigate", "playwright")):
            return "browser", "dom-automation", "browser-worker", ["browser_intent"]
        if any(term in text for term in ("windows", "desktop", "uia", "wps", "office")):
            return "windows", "local-windows", "windows-worker", ["desktop_intent"]
        if any(term in text for term in ("research", "compare sources", "multi-step", "complex")):
            return "complex", "hermes-supervisor", "hermes", ["complex_planning"]
        if any(term in text for term in ("privacy", "pii", "secretref")):
            return "privacy", "local-privacy", "privacy-worker", ["privacy_intent"]
        return "simple", "qwen2.5:7b", "text-worker", ["simple_text"]
