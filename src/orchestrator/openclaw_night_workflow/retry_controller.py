from __future__ import annotations

from dataclasses import dataclass

from .security import is_low_risk_action


@dataclass
class RetryDecision:
    should_retry: bool
    reason: str
    next_attempt: int


def decide_retry(current_attempt: int, max_retries: int, findings: list[str]) -> RetryDecision:
    if current_attempt >= max_retries:
        return RetryDecision(False, "retry_limit_reached", current_attempt)
    if not findings:
        return RetryDecision(False, "no_retryable_findings", current_attempt)
    unsafe = [finding for finding in findings if not is_low_risk_action(finding)]
    if unsafe:
        return RetryDecision(False, "unsafe_retry_finding", current_attempt)
    return RetryDecision(True, "low_risk_retry_allowed", current_attempt + 1)

