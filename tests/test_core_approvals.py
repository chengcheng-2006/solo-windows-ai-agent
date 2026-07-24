"""Tests for approval engine — create, resolve, nonce verification."""
import pytest

from solo.core.approvals import create_approval, resolve_approval
from solo.core.task_store import TaskStore


@pytest.fixture
def store(tmp_path):
    s = TaskStore(tmp_path / "test.db")
    s.migrate()
    yield s
    s.close()


@pytest.fixture
def run_id(store):
    return store.create_workflow_run("test-wf", idempotency_key="approval-test-001")


def test_create_approval(store, run_id):
    result = create_approval(
        store=store,
        workflow_id="test-wf",
        run_id=run_id,
        phase_id="review",
        risk="R3",
        target="delete important file",
    )
    assert "action_id" in result
    assert "nonce" in result
    assert "expires_at" in result
    assert result["action_id"].startswith("act-")
    assert len(result["nonce"]) == 64  # 32 bytes hex


def test_create_and_approve(store, run_id):
    approval = create_approval(
        store=store, workflow_id="test-wf", run_id=run_id,
        phase_id="review", risk="R3", target="delete file",
    )
    resolved = resolve_approval(
        store=store,
        action_id=approval["action_id"],
        nonce=approval["nonce"],
        approve=True,
        owner_confirmed=True,
    )
    assert resolved is True
    row = store.conn.execute(
        "SELECT status FROM approvals WHERE action_id = ?",
        (approval["action_id"],),
    ).fetchone()
    assert row["status"] == "APPROVED"


def test_create_and_reject(store, run_id):
    approval = create_approval(
        store=store, workflow_id="test-wf", run_id=run_id,
        phase_id="review", risk="R3", target="delete file",
    )
    resolved = resolve_approval(
        store=store,
        action_id=approval["action_id"],
        nonce=approval["nonce"],
        approve=False,
        owner_confirmed=True,
    )
    assert resolved is True
    row = store.conn.execute(
        "SELECT status FROM approvals WHERE action_id = ?",
        (approval["action_id"],),
    ).fetchone()
    assert row["status"] == "REJECTED"


def test_wrong_nonce_rejected(store, run_id):
    approval = create_approval(
        store=store, workflow_id="test-wf", run_id=run_id,
        phase_id="review", risk="R3", target="delete file",
    )
    resolved = resolve_approval(
        store=store,
        action_id=approval["action_id"],
        nonce="wrong-nonce-value",
        approve=True,
        owner_confirmed=True,
    )
    assert resolved is False
    row = store.conn.execute(
        "SELECT status FROM approvals WHERE action_id = ?",
        (approval["action_id"],),
    ).fetchone()
    assert row["status"] == "PENDING"  # Not consumed


def test_nonexistent_approval(store):
    resolved = resolve_approval(
        store=store,
        action_id="act-nonexistent",
        nonce="abc",
        approve=True,
        owner_confirmed=True,
    )
    assert resolved is False


def test_double_approve_fails(store, run_id):
    approval = create_approval(
        store=store, workflow_id="test-wf", run_id=run_id,
        phase_id="review", risk="R3", target="delete file",
    )
    # First resolve should succeed
    r1 = resolve_approval(store, approval["action_id"], approval["nonce"], approve=True, owner_confirmed=True)
    assert r1 is True
    # Second resolve should fail (already consumed)
    r2 = resolve_approval(store, approval["action_id"], approval["nonce"], approve=False, owner_confirmed=True)
    assert r2 is False


def test_without_owner_confirmation(store, run_id):
    approval = create_approval(
        store=store, workflow_id="test-wf", run_id=run_id,
        phase_id="review", risk="R3", target="delete file",
    )
    resolved = resolve_approval(
        store=store,
        action_id=approval["action_id"],
        nonce=approval["nonce"],
        approve=True,
        owner_confirmed=False,  # Not confirmed
    )
    assert resolved is False
