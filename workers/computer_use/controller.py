from __future__ import annotations

from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from .control import ControlStatus, UserControlState
from .models import (
    ActionExecution,
    ActionPlan,
    ActionValidation,
    ComputerAction,
    ControllerResult,
    Observation,
    ObservationScope,
)
from .policy import ComputerUsePolicy


class ObservationProvider(Protocol):
    def observe(self, scope: ObservationScope) -> Observation: ...


class ActionExecutor(Protocol):
    def execute(
        self,
        action: ComputerAction,
        observation: Observation,
        cancellation_requested: Callable[[], bool],
    ) -> ActionExecution: ...


class ResultValidator(Protocol):
    def validate(
        self,
        before: Observation,
        action: ComputerAction,
        execution: ActionExecution,
        after: Observation,
    ) -> ActionValidation: ...


ActionPlanner = Callable[[Observation, int], ActionPlan]


class ComputerUseController:
    """Observe -> plan -> policy -> execute -> observe -> validate controller."""

    def __init__(
        self,
        observer: ObservationProvider,
        executor: ActionExecutor,
        validator: ResultValidator,
        policy: ComputerUsePolicy | None = None,
        user_control: UserControlState | None = None,
    ) -> None:
        self.observer = observer
        self.executor = executor
        self.validator = validator
        self.policy = policy or ComputerUsePolicy()
        self.user_control = user_control or UserControlState()

    @staticmethod
    def _paused_result(task_id: UUID, attempts: int, observations: list[UUID], actions: list[UUID], status: ControlStatus, reason: str) -> ControllerResult:
        return ControllerResult(
            status="EMERGENCY_STOPPED" if status == ControlStatus.EMERGENCY_STOPPED else "PAUSED_BY_USER",
            task_id=task_id,
            attempts=attempts,
            observation_ids=observations,
            action_ids=actions,
            reason_code=reason,
        )

    def run(
        self,
        task_id: UUID,
        scope: ObservationScope,
        planner: ActionPlanner,
        *,
        max_attempts: int = 1,
    ) -> ControllerResult:
        if max_attempts < 1 or max_attempts > self.policy.config.max_attempts:
            raise ValueError("max_attempts exceeds policy retry ceiling")
        observation_ids: list[UUID] = []
        action_ids: list[UUID] = []
        last_execution: ActionExecution | None = None
        last_validation: ActionValidation | None = None
        attempts = 0

        for attempt in range(1, max_attempts + 1):
            state = self.user_control.snapshot()
            if state.status != ControlStatus.ACTIVE:
                return self._paused_result(task_id, attempts, observation_ids, action_ids, state.status, state.reason_code)
            before = self.observer.observe(scope)
            observation_ids.append(before.observation_id)
            if self.policy.is_protected_window(before):
                state = self.user_control.signal_protected_window()
                return self._paused_result(task_id, attempts, observation_ids, action_ids, state.status, state.reason_code)
            guard = self.user_control.snapshot()
            plan = planner(before, attempt)
            action = plan.action
            if action.task_id != task_id:
                raise ValueError("planner returned an action for a different task")
            action_ids.append(action.action_id)
            decision = self.policy.evaluate(action, before, plan.approval, attempt=attempt)
            if not decision.allowed:
                if decision.should_pause:
                    state = self.user_control.request_takeover(decision.code)
                    return self._paused_result(task_id, attempts, observation_ids, action_ids, state.status, decision.code)
                return ControllerResult(
                    status="POLICY_DENIED",
                    task_id=task_id,
                    attempts=attempts,
                    observation_ids=observation_ids,
                    action_ids=action_ids,
                    policy_decision=decision,
                    reason_code=decision.code,
                )
            if not self.user_control.is_unchanged_and_active(guard):
                state = self.user_control.snapshot()
                return self._paused_result(task_id, attempts, observation_ids, action_ids, state.status, state.reason_code)
            attempts += 1
            last_execution = self.executor.execute(action, before, self.user_control.cancellation_requested)
            state = self.user_control.snapshot()
            if state.status != ControlStatus.ACTIVE or last_execution.status in {"PAUSED", "ABORTED"}:
                return self._paused_result(task_id, attempts, observation_ids, action_ids, state.status, state.reason_code)
            if last_execution.status != "PASS":
                if attempt < max_attempts:
                    continue
                return ControllerResult(
                    status="EXECUTION_FAILED",
                    task_id=task_id,
                    attempts=attempts,
                    observation_ids=observation_ids,
                    action_ids=action_ids,
                    policy_decision=decision,
                    execution=last_execution,
                    reason_code=last_execution.result_code,
                )
            after = self.observer.observe(scope)
            observation_ids.append(after.observation_id)
            if self.policy.is_protected_window(after):
                state = self.user_control.signal_protected_window()
                return self._paused_result(task_id, attempts, observation_ids, action_ids, state.status, state.reason_code)
            last_validation = self.validator.validate(before, action, last_execution, after)
            if last_validation.passed:
                return ControllerResult(
                    status="PASS",
                    task_id=task_id,
                    attempts=attempts,
                    observation_ids=observation_ids,
                    action_ids=action_ids,
                    policy_decision=decision,
                    execution=last_execution,
                    validation=last_validation,
                    reason_code="VALIDATED",
                )
            if attempt < max_attempts:
                continue

        return ControllerResult(
            status="VALIDATION_FAILED",
            task_id=task_id,
            attempts=attempts,
            observation_ids=observation_ids,
            action_ids=action_ids,
            execution=last_execution,
            validation=last_validation,
            reason_code=last_validation.code if last_validation else "VALIDATION_NOT_RUN",
        )
