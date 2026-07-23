from __future__ import annotations

from collections.abc import Iterable

from .errors import ReviewRejected
from .models import (
    AuditEvent,
    Department,
    FormalTask,
    FormalTaskState,
    Memorial,
    PlanReviewBundle,
    ReviewDecision,
    ReviewRecord,
    ReviewStage,
)
from .registry import AgentRegistry


class ReviewGate:
    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    def validate_reviewer(self, review: ReviewRecord) -> None:
        reviewer = self.registry.get(review.reviewer_agent_id)
        if reviewer.department != Department.MENXIA:
            raise ReviewRejected("reviewer_not_menxia", "review must be performed by Menxia")
        if reviewer.role != review.reviewer_role:
            raise ReviewRejected("reviewer_role_mismatch", "reviewer role does not match the registry")

    def validate_plan_review(self, task: FormalTask, review: PlanReviewBundle) -> None:
        for item in review.reviews:
            self.validate_reviewer(item)
        if review.task_id != task.task_id:
            raise ReviewRejected("plan_review_task_mismatch", "plan review is bound to another task")
        if review.plan_revision != task.plan_revision:
            raise ReviewRejected("plan_review_revision_mismatch", "plan review is bound to another revision")

    def validate_final_review(self, task: FormalTask, review: ReviewRecord) -> None:
        self.validate_reviewer(review)
        if review.task_id != task.task_id:
            raise ReviewRejected("final_review_task_mismatch", "final review is bound to another task")
        if review.stage != ReviewStage.FINAL:
            raise ReviewRejected("final_review_stage_invalid", "final review stage is invalid")
        if review.plan_revision != task.plan_revision:
            raise ReviewRejected("final_review_revision_mismatch", "final review is bound to another revision")
        if review.reviewer_role != "result_validator":
            raise ReviewRejected("final_review_requires_result_validator", "final review requires the independent result validator")


class MemorialBuilder:
    def __init__(self, review_gate: ReviewGate):
        self.review_gate = review_gate

    def build(
        self,
        *,
        task: FormalTask,
        final_review: ReviewRecord,
        title: str,
        summary: str,
        evidence_refs: tuple[str, ...],
        audit_events: Iterable[AuditEvent],
        artifact_refs: tuple[str, ...] = (),
        known_limitations: tuple[str, ...] = (),
    ) -> Memorial:
        self.review_gate.validate_final_review(task, final_review)
        if task.current_state != FormalTaskState.COMPLETED:
            raise ReviewRejected("memorial_task_not_completed", "final memorial requires a completed task")
        if final_review.decision != ReviewDecision.APPROVED:
            raise ReviewRejected("memorial_final_review_not_approved", "final memorial requires final approval")
        if task.final_review_id != final_review.review_id:
            raise ReviewRejected("memorial_review_binding_mismatch", "final review does not match task completion")
        event_ids = tuple(event.event_id for event in audit_events if event.task_id == task.task_id)
        if not event_ids:
            raise ReviewRejected("memorial_audit_missing", "final memorial requires task audit events")
        return Memorial(
            task_id=task.task_id,
            task_state=task.current_state,
            plan_revision=task.plan_revision,
            title=title,
            summary=summary,
            final_review_id=final_review.review_id,
            evidence_refs=evidence_refs,
            artifact_refs=artifact_refs,
            audit_event_ids=event_ids,
            known_limitations=known_limitations,
        )
