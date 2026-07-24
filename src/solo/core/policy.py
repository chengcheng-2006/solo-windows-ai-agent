"""Policy engine — evaluates risk assessment against access policies.

Determines: allowed, requires_approval, and approval_scope.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .enums import RiskLevel


@dataclass
class PolicyDecision:
    """Result of a policy evaluation."""
    allowed: bool
    requires_approval: bool
    approval_scope: str = ""  # "task" or "step"
    reason_code: str = ""
    denied_reasons: tuple[str, ...] = field(default_factory=tuple)


class PolicyEngine:
    """Evaluate whether a task is allowed and what approval it needs.

    Rules:
    - R0 / R1: auto-approved, no approval needed
    - R2: requires task-level approval
    - R3: requires step-level approval
    """

    def evaluate(
        self,
        requester: str,
        owner_id: str,
        source_channel: str,
        risk: RiskLevel,
    ) -> PolicyDecision:
        """Evaluate a risk level against policy rules."""
        if risk == RiskLevel.R0:
            return PolicyDecision(
                allowed=True,
                requires_approval=False,
                reason_code="R0_read_only_safe",
            )

        if risk == RiskLevel.R1:
            return PolicyDecision(
                allowed=True,
                requires_approval=False,
                reason_code="R1_minimal_risk",
            )

        if risk == RiskLevel.R2:
            return PolicyDecision(
                allowed=True,
                requires_approval=True,
                approval_scope="task",
                reason_code="R2_requires_approval",
            )

        if risk == RiskLevel.R3:
            return PolicyDecision(
                allowed=True,
                requires_approval=True,
                approval_scope="step",
                reason_code="R3_requires_step_approval",
            )

        # Unknown risk level — deny closed
        return PolicyDecision(
            allowed=False,
            requires_approval=False,
            reason_code="unknown_risk_deny_closed",
            denied_reasons=(f"Unknown risk level: {risk}",),
        )
