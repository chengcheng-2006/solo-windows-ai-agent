from __future__ import annotations

from dataclasses import dataclass

from .enums import RiskLevel


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    approval_scope: str | None
    reason_code: str


class PolicyEngine:
    def evaluate(self, requester: str, owner_id: str, source_channel: str, risk: RiskLevel) -> PolicyDecision:
        if requester != owner_id:
            return PolicyDecision(False, False, None, "requester_not_owner")
        if "group" in source_channel.lower():
            return PolicyDecision(False, False, None, "group_policy_disabled")
        if risk in {RiskLevel.R0, RiskLevel.R1}:
            return PolicyDecision(True, False, None, "owner_low_risk_allowed")
        if risk == RiskLevel.R2:
            return PolicyDecision(True, True, "task", "task_approval_required")
        return PolicyDecision(True, True, "step", "per_action_approval_required")

