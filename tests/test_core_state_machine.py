"""Tests for state_machine module — all legal and illegal transitions."""
import pytest

from solo.core.state_machine import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATES,
    can_transition,
    require_transition,
    InvalidTransition,
)


def test_can_transition_legal():
    assert can_transition("RECEIVED", "TRIAGED") is True
    assert can_transition("RECEIVED", "REJECTED") is True
    assert can_transition("TRIAGED", "PLANNING") is True
    assert can_transition("TRIAGED", "REVIEW_PENDING") is True
    assert can_transition("TRIAGED", "REJECTED") is True
    assert can_transition("PLANNING", "DISPATCHED") is True
    assert can_transition("REVIEW_PENDING", "APPROVED") is True
    assert can_transition("REVIEW_PENDING", "REJECTED") is True
    assert can_transition("APPROVED", "DISPATCHED") is True
    assert can_transition("DISPATCHED", "EXECUTING") is True
    assert can_transition("EXECUTING", "VALIDATING") is True
    assert can_transition("VALIDATING", "COMPLETED") is True


def test_can_transition_illegal():
    # Skip states
    assert can_transition("RECEIVED", "DISPATCHED") is False
    assert can_transition("TRIAGED", "COMPLETED") is False
    assert can_transition("REVIEW_PENDING", "DISPATCHED") is False
    # Reverse
    assert can_transition("TRIAGED", "RECEIVED") is False
    assert can_transition("COMPLETED", "VALIDATING") is False
    # Same state
    assert can_transition("RECEIVED", "RECEIVED") is False


def test_terminal_states():
    assert "REJECTED" in TERMINAL_STATES
    assert "COMPLETED" in TERMINAL_STATES
    for state in ALLOWED_TRANSITIONS:
        if state in TERMINAL_STATES:
            assert len(ALLOWED_TRANSITIONS[state]) == 0


def test_terminal_from_terminal():
    assert can_transition("REJECTED", "DISPATCHED") is False
    assert can_transition("REJECTED", "EXECUTING") is False
    assert can_transition("COMPLETED", "COMPLETED") is False


def test_require_transition_legal():
    # Should not raise
    require_transition("RECEIVED", "TRIAGED")
    require_transition("EXECUTING", "VALIDATING")


def test_require_transition_illegal():
    with pytest.raises(InvalidTransition):
        require_transition("RECEIVED", "COMPLETED")
    with pytest.raises(InvalidTransition):
        require_transition("APPROVED", "REJECTED")


def test_all_states_have_transition_entries():
    expected = {"RECEIVED", "TRIAGED", "PLANNING", "REVIEW_PENDING",
                "APPROVED", "REJECTED", "DISPATCHED", "EXECUTING",
                "VALIDATING", "COMPLETED"}
    assert set(ALLOWED_TRANSITIONS.keys()) == expected


def test_no_unknown_targets():
    known = {"RECEIVED", "TRIAGED", "PLANNING", "REVIEW_PENDING",
             "APPROVED", "REJECTED", "DISPATCHED", "EXECUTING",
             "VALIDATING", "COMPLETED"}
    for source, targets in ALLOWED_TRANSITIONS.items():
        for t in targets:
            assert t in known, f"{source} -> {t}: {t} is not a known state"


@pytest.mark.parametrize("state", ["RECEIVED", "TRIAGED", "APPROVED", "COMPLETED"])
def test_allowed_transitions_contain_self_in_key(state):
    assert state in ALLOWED_TRANSITIONS
