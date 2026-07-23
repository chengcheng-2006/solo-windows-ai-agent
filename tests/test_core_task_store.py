"""Tests for TaskStore — CRUD, state transitions, events, execution attempts."""
import pytest
from pathlib import Path

from solo.core.task_store import TaskStore


@pytest.fixture
def store(tmp_path):
    s = TaskStore(tmp_path / "test.db")
    s.migrate()
    yield s
    s.close()


def test_create_run(store):
    run_id = store.create_workflow_run("test-wf", idempotency_key="idem-001")
    assert run_id.startswith("run-")
    assert len(run_id) == 16  # run- + 12 hex chars

    run = store.get_run(run_id)
    assert run is not None
    assert run["workflow_id"] == "test-wf"
    assert run["state"] == "RECEIVED"


def test_create_run_with_payload(store):
    run_id = store.create_workflow_run("test-wf", payload={"key": "value"})
    run = store.get_run(run_id)
    assert run is not None
    assert run["payload"] == {"key": "value"}


def test_transition_run(store):
    run_id = store.create_workflow_run("test-wf")
    store.transition_run(run_id, "TRIAGED")
    run = store.get_run(run_id)
    assert run["state"] == "TRIAGED"


def test_transition_with_payload(store):
    run_id = store.create_workflow_run("test-wf")
    store.transition_run(run_id, "TRIAGED", payload={"risk": "R0"})
    run = store.get_run(run_id)
    assert run["payload"]["risk"] == "R0"


def test_get_nonexistent_run(store):
    assert store.get_run("run-nonexistent") is None


def test_append_event(store):
    run_id = store.create_workflow_run("test-wf")
    store.append_event(run_id, "RECEIVED", detail="Task created")
    events = store.get_events(run_id)
    assert len(events) == 1
    assert events[0]["state"] == "RECEIVED"


def test_append_multiple_events(store):
    run_id = store.create_workflow_run("test-wf")
    store.append_event(run_id, "RECEIVED")
    store.append_event(run_id, "TRIAGED", ok=True, detail="R0")
    events = store.get_events(run_id)
    assert len(events) == 2


def test_record_execution_attempt(store):
    from solo.core.schemas import utc_now
    run_id = store.create_workflow_run("test-wf")
    store.record_execution_attempt(
        run_id=run_id,
        phase_id="exec",
        attempt=1,
        executor="test",
        task_id="task-001",
        started_at=utc_now(),
        finished_at=utc_now(),
        exit_code=0,
    )
    rows = store.conn.execute(
        "SELECT COUNT(*) as c FROM execution_attempts WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    assert rows["c"] == 1


def test_record_validation(store):
    run_id = store.create_workflow_run("test-wf")
    validation = {
        "validation_id": "val-001",
        "run_id": run_id,
        "phase_id": "phase-1",
        "result": "PASS",
        "checks_total": 4,
        "checks_passed": 4,
        "checks_failed": 0,
    }
    store.record_validation(validation)
    rows = store.conn.execute(
        "SELECT COUNT(*) as c FROM validation_runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    assert rows["c"] == 1


def test_create_approval_record(store):
    run_id = store.create_workflow_run("test-wf")
    store.create_approval_record(
        action_id="act-001",
        run_id=run_id,
        workflow_id="test-wf",
        phase_id="review",
        risk="R3",
        target="delete file",
        nonce="abc123",
    )
    row = store.conn.execute(
        "SELECT status FROM approvals WHERE action_id = ?",
        ("act-001",),
    ).fetchone()
    assert row["status"] == "PENDING"


def test_resolve_approval_record(store):
    run_id = store.create_workflow_run("test-wf")
    store.create_approval_record(
        action_id="act-002",
        run_id=run_id,
        workflow_id="test-wf",
        phase_id="review",
        risk="R3",
        target="delete file",
        nonce="abc123",
    )
    ok = store.resolve_approval_record("act-002", "REJECTED")
    assert ok is True
    row = store.conn.execute(
        "SELECT status FROM approvals WHERE action_id = ?",
        ("act-002",),
    ).fetchone()
    assert row["status"] == "REJECTED"


def test_context_manager(tmp_path):
    with TaskStore(tmp_path / "ctx.db") as store:
        store.migrate()
        run_id = store.create_workflow_run("ctx-test")
        assert run_id is not None


def test_connection_reuse(store):
    c1 = store.connect()
    c2 = store.connect()
    assert c1 is c2


def test_migrate_idempotent(store):
    # Running migrate twice should not raise
    store.migrate()
    store.migrate()
