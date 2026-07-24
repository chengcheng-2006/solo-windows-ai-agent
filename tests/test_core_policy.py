"""Tests for policy engine — R0 auto-approve, R2 approval, R3 step-approval."""
import pytest

from solo.core.enums import RiskLevel
from solo.core.policy import PolicyEngine


@pytest.fixture
def engine():
    return PolicyEngine()


def test_r0_auto_approved(engine):
    d = engine.evaluate("user", "user", "test", RiskLevel.R0)
    assert d.allowed is True
    assert d.requires_approval is False
    assert d.reason_code == "R0_read_only_safe"


def test_r1_auto_approved(engine):
    d = engine.evaluate("user", "user", "test", RiskLevel.R1)
    assert d.allowed is True
    assert d.requires_approval is False
    assert d.reason_code == "R1_minimal_risk"


def test_r2_requires_approval(engine):
    d = engine.evaluate("user", "user", "test", RiskLevel.R2)
    assert d.allowed is True
    assert d.requires_approval is True
    assert d.approval_scope == "task"
    assert d.reason_code == "R2_requires_approval"


def test_r3_requires_step_approval(engine):
    d = engine.evaluate("user", "user", "test", RiskLevel.R3)
    assert d.allowed is True
    assert d.requires_approval is True
    assert d.approval_scope == "step"
    assert d.reason_code == "R3_requires_step_approval"


def test_all_levels_evaluated(engine):
    for level in RiskLevel:
        d = engine.evaluate("user", "user", "test", level)
        assert d.reason_code != "", f"No reason for {level}"


def test_unknown_risk_deny_closed(engine):
    d = engine.evaluate("user", "user", "test", "UNKNOWN")  # type: ignore[arg-type]
    assert d.allowed is False
    assert d.requires_approval is False
    assert "unknown_risk_deny_closed" in d.reason_code
