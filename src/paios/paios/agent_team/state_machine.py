from __future__ import annotations

from typing import Any

from .audit import AuditSink, audit_event
from .errors import AgentTeamError, AuthorizationDenied, InvalidStateTransition, ReviewRejected
from .models import (
    Department,
    FormalTask,
    FormalTaskState,
    PlanReviewBundle,
    ReviewDecision,
    ReviewRecord,
    utc_now,
)
from .registry import AgentRegistry
from .review import ReviewGate


ALLOWED_TRANSITIONS: dict[FormalTaskState, frozenset[FormalTaskState]] = {
    FormalTaskState.RECEIVED: frozenset({FormalTaskState.TRIAGED, FormalTaskState.PAUSED, FormalTaskState.CANCELLED, FormalTaskState.FAILED}),
    FormalTaskState.TRIAGED: frozenset({FormalTaskState.PLANNING, FormalTaskState.PAUSED, FormalTaskState.BLOCKED, FormalTaskState.CANCELLED, FormalTaskState.FAILED}),
    FormalTaskState.PLANNING: frozenset({FormalTaskState.REVIEW_PENDING, FormalTaskState.PAUSED, FormalTaskState.BLOCKED, FormalTaskState.WAITING_USER_APPROVAL, FormalTaskState.CANCELLED, FormalTaskState.FAILED}),
    FormalTaskState.REVIEW_PENDING: frozenset({FormalTaskState.APPROVED, FormalTaskState.VETOED, FormalTaskState.WAITING_USER_APPROVAL, FormalTaskState.CANCELLED, FormalTaskState.FAILED}),
    FormalTaskState.APPROVED: frozenset({FormalTaskState.DISPATCHED, FormalTaskState.PAUSED, FormalTaskState.CANCELLED, FormalTaskState.FAILED}),
    FormalTaskState.DISPATCHED: frozenset({FormalTaskState.EXECUTING, FormalTaskState.PAUSED, FormalTaskState.BLOCKED, FormalTaskState.RETRYING, FormalTaskState.CANCELLED, FormalTaskState.FAILED}),
    FormalTaskState.EXECUTING: frozenset({FormalTaskState.VALIDATING, FormalTaskState.PAUSED, FormalTaskState.BLOCKED, FormalTaskState.RETRYING, FormalTaskState.RECOVERING, FormalTaskState.WAITING_USER_APPROVAL, FormalTaskState.CANCELLED, FormalTaskState.FAILED}),
    FormalTaskState.VALIDATING: frozenset({FormalTaskState.COMPLETED, FormalTaskState.RETRYING, FormalTaskState.WAITING_USER_APPROVAL, FormalTaskState.CANCELLED, FormalTaskState.FAILED}),
    FormalTaskState.VETOED: frozenset({FormalTaskState.PLANNING}),
    FormalTaskState.WAITING_USER_APPROVAL: frozenset({FormalTaskState.PLANNING, FormalTaskState.REVIEW_PENDING, FormalTaskState.EXECUTING, FormalTaskState.VALIDATING, FormalTaskState.PAUSED, FormalTaskState.CANCELLED, FormalTaskState.FAILED}),
    FormalTaskState.PAUSED: frozenset({FormalTaskState.TRIAGED, FormalTaskState.PLANNING, FormalTaskState.APPROVED, FormalTaskState.DISPATCHED, FormalTaskState.EXECUTING, FormalTaskState.VALIDATING, FormalTaskState.CANCELLED, FormalTaskState.FAILED}),
    FormalTaskState.BLOCKED: frozenset({FormalTaskState.RECOVERING, FormalTaskState.PAUSED, FormalTaskState.CANCELLED, FormalTaskState.FAILED}),
    FormalTaskState.RETRYING: frozenset({FormalTaskState.DISPATCHED, FormalTaskState.EXECUTING, FormalTaskState.RECOVERING, FormalTaskState.CANCELLED, FormalTaskState.FAILED}),
    FormalTaskState.RECOVERING: frozenset({FormalTaskState.DISPATCHED, FormalTaskState.EXECUTING, FormalTaskState.RETRYING, FormalTaskState.PAUSED, FormalTaskState.CANCELLED, FormalTaskState.FAILED}),
    FormalTaskState.COMPLETED: frozenset(),
    FormalTaskState.FAILED: frozenset(),
    FormalTaskState.CANCELLED: frozenset(),
}


INTERRUPTION_STATES = {
    FormalTaskState.WAITING_USER_APPROVAL,
    FormalTaskState.PAUSED,
    FormalTaskState.BLOCKED,
    FormalTaskState.RETRYING,
    FormalTaskState.RECOVERING,
}


TARGET_AUTHORITY: dict[FormalTaskState, Department] = {
    FormalTaskState.TRIAGED: Department.TAIZI,
    FormalTaskState.PLANNING: Department.ZHONGSHU,
    FormalTaskState.REVIEW_PENDING: Department.ZHONGSHU,
    FormalTaskState.APPROVED: Department.MENXIA,
    FormalTaskState.VETOED: Department.MENXIA,
    FormalTaskState.DISPATCHED: Department.SHANGSHU,
    FormalTaskState.EXECUTING: Department.SHANGSHU,
    FormalTaskState.VALIDATING: Department.SHANGSHU,
    FormalTaskState.COMPLETED: Department.MENXIA,
    FormalTaskState.RETRYING: Department.SHANGSHU,
    FormalTaskState.RECOVERING: Department.SHANGSHU,
}


class DeterministicTaskStateMachine:
    def __init__(self, registry: AgentRegistry, audit: AuditSink):
        self.registry = registry
        self.audit = audit
        self.reviews = ReviewGate(registry)
        self.owner_actor_id = registry.document.owner_actor_id

    def transition(
        self,
        task: FormalTask,
        target: FormalTaskState,
        *,
        actor_id: str,
        reason_code: str,
        review: ReviewRecord | PlanReviewBundle | None = None,
        expected_version: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FormalTask:
        try:
            if expected_version is not None and expected_version != task.state_version:
                raise InvalidStateTransition("state_version_conflict", "task state version changed")
            if target not in ALLOWED_TRANSITIONS[task.current_state]:
                raise InvalidStateTransition(
                    "illegal_state_transition",
                    f"invalid formal task transition: {task.current_state.value} -> {target.value}",
                )
            self._authorize_actor(task, target, actor_id, review)
            review_id = self._validate_review_gate(task, target, review)
            self._validate_resume_target(task, target)
        except AgentTeamError as exc:
            self.audit.record(
                audit_event(
                    actor_id=actor_id,
                    event_type="task.transition_denied",
                    outcome="DENIED",
                    reason_code=exc.code,
                    task_id=task.task_id,
                    from_state=task.current_state,
                    to_state=target,
                )
            )
            raise

        update: dict[str, Any] = {
            "current_state": target,
            "state_version": task.state_version + 1,
            "updated_at": utc_now(),
        }
        if target in INTERRUPTION_STATES:
            update["interrupted_from"] = task.current_state
        elif task.current_state in INTERRUPTION_STATES:
            update["interrupted_from"] = None
        if task.current_state == FormalTaskState.VETOED and target == FormalTaskState.PLANNING:
            update["plan_revision"] = task.plan_revision + 1
            update["approved_plan_review_id"] = None
        if target == FormalTaskState.APPROVED:
            update["approved_plan_review_id"] = review_id
        if target == FormalTaskState.COMPLETED:
            update["final_review_id"] = review_id
        updated = task.model_copy(update=update)
        self.audit.record(
            audit_event(
                actor_id=actor_id,
                event_type="task.state_changed",
                outcome="ALLOWED",
                reason_code=reason_code,
                task_id=task.task_id,
                from_state=task.current_state,
                to_state=target,
                payload={
                    "state_version": updated.state_version,
                    "plan_revision": updated.plan_revision,
                    "review_id": str(review_id) if review_id else None,
                    "metadata": metadata or {},
                },
            )
        )
        return updated

    def _authorize_actor(
        self,
        task: FormalTask,
        target: FormalTaskState,
        actor_id: str,
        review: ReviewRecord | PlanReviewBundle | None,
    ) -> None:
        if target in {FormalTaskState.PAUSED, FormalTaskState.BLOCKED, FormalTaskState.WAITING_USER_APPROVAL, FormalTaskState.FAILED, FormalTaskState.CANCELLED}:
            if actor_id == self.owner_actor_id:
                return
            actor = self.registry.get(actor_id)
            if actor.department != Department.SHANGSHU:
                raise AuthorizationDenied("lifecycle_transition_requires_shangshu_or_owner", "lifecycle transition is not authorized")
            return

        expected = TARGET_AUTHORITY.get(target)
        if expected is None:
            raise AuthorizationDenied("state_authority_undefined", "state transition authority is undefined")
        actor = self.registry.get(actor_id)

        # A Menxia final veto sends validation back for deterministic retry.
        if (
            task.current_state == FormalTaskState.VALIDATING
            and target == FormalTaskState.RETRYING
            and review is not None
            and isinstance(review, ReviewRecord)
            and review.decision == ReviewDecision.VETOED
        ):
            expected = Department.MENXIA
        if actor.department != expected:
            if target == FormalTaskState.COMPLETED and actor.is_worker:
                raise AuthorizationDenied("worker_cannot_complete_task", "workers cannot mark formal tasks completed")
            raise AuthorizationDenied("state_transition_actor_forbidden", "actor cannot perform this state transition")
        if target == FormalTaskState.COMPLETED and actor.role != "result_validator":
            raise AuthorizationDenied("completion_requires_result_validator", "completion requires Menxia result validator")

    def _validate_review_gate(
        self,
        task: FormalTask,
        target: FormalTaskState,
        review: ReviewRecord | PlanReviewBundle | None,
    ) -> object | None:
        if target in {FormalTaskState.APPROVED, FormalTaskState.VETOED}:
            if not isinstance(review, PlanReviewBundle):
                raise ReviewRejected("plan_review_required", "plan review is required")
            self.reviews.validate_plan_review(task, review)
            allowed = (
                {ReviewDecision.APPROVED, ReviewDecision.APPROVED_WITH_CONDITIONS}
                if target == FormalTaskState.APPROVED
                else {ReviewDecision.VETOED}
            )
            if review.decision not in allowed:
                raise ReviewRejected("plan_review_decision_invalid", "plan review decision does not match target state")
            return review.bundle_id
        if target == FormalTaskState.COMPLETED:
            if not isinstance(review, ReviewRecord):
                raise ReviewRejected("final_review_required", "final review is required")
            self.reviews.validate_final_review(task, review)
            if review.decision != ReviewDecision.APPROVED:
                raise ReviewRejected("final_review_not_approved", "only final APPROVED can complete a task")
            return review.review_id
        if task.current_state == FormalTaskState.VALIDATING and target == FormalTaskState.RETRYING and isinstance(review, ReviewRecord):
            self.reviews.validate_final_review(task, review)
            if review.decision != ReviewDecision.VETOED:
                raise ReviewRejected("final_retry_requires_veto", "validation retry requires a final veto")
            return review.review_id
        if target == FormalTaskState.WAITING_USER_APPROVAL and task.current_state == FormalTaskState.REVIEW_PENDING:
            if not isinstance(review, PlanReviewBundle):
                raise ReviewRejected("human_approval_review_required", "Menxia must request human approval")
            self.reviews.validate_plan_review(task, review)
            if review.decision != ReviewDecision.HUMAN_APPROVAL_REQUIRED:
                raise ReviewRejected("human_approval_decision_required", "review decision must require human approval")
            return review.bundle_id
        return None

    @staticmethod
    def _validate_resume_target(task: FormalTask, target: FormalTaskState) -> None:
        if task.current_state in {FormalTaskState.PAUSED, FormalTaskState.WAITING_USER_APPROVAL}:
            administrative = {FormalTaskState.PAUSED, FormalTaskState.CANCELLED, FormalTaskState.FAILED}
            if target not in administrative and task.interrupted_from is not None and target != task.interrupted_from:
                raise InvalidStateTransition("resume_state_mismatch", "task must resume at its interrupted state")
