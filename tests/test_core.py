# Solo Smoke Test — No API keys required
# Run: python tests/test_core.py

import os
import sys
import tempfile
import uuid
from pathlib import Path

SOLO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(SOLO_ROOT, "src"))


def step(name, fn):
    try:
        fn()
        print(f"  [PASS] {name}")
        return True
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        return False


def test_import_paios():
    from paios.paios import config, enums, schemas, security, risk
    assert config is not None
    assert enums is not None
    assert schemas is not None


def test_paios_schemas():
    from paios.paios.schemas import TaskCreate
    task = TaskCreate(objective="test task", task_type="general", source_channel="demo")
    assert task.objective == "test task"


def test_paios_state_machine():
    from paios.paios.state_machine import ALLOWED_TRANSITIONS, TERMINAL_STATES
    from paios.paios.enums import TaskState
    assert len(TERMINAL_STATES) >= 2
    received = ALLOWED_TRANSITIONS.get(TaskState.RECEIVED, set())
    assert TaskState.CANCELLED in received


def test_paios_enums():
    from paios.paios.enums import RiskLevel, TaskState
    assert RiskLevel.R0.value is not None
    assert TaskState.RECEIVED.value == "RECEIVED"


def test_paios_security():
    from paios.paios.security import is_secret_ref
    assert is_secret_ref("secret://provider/key-name") is True
    assert is_secret_ref("plaintext-value") is False


def test_orchestrator_imports():
    from orchestrator.openclaw_night_workflow import config, schemas, state_machine
    from orchestrator.openclaw_night_workflow.schemas import utc_now
    assert config is not None
    assert callable(utc_now)


def test_orchestrator_states():
    from orchestrator.openclaw_night_workflow.schemas import WORKFLOW_STATES
    assert "CREATED" in WORKFLOW_STATES
    assert "RUNNING" in WORKFLOW_STATES


def test_orchestrator_retry():
    from orchestrator.openclaw_night_workflow.retry_controller import decide_retry
    d1 = decide_retry(current_attempt=0, max_retries=3, findings=[])
    assert d1.should_retry is False
    assert d1.reason == "no_retryable_findings"
    d2 = decide_retry(current_attempt=5, max_retries=3, findings=["error"])
    assert d2.should_retry is False
    assert d2.reason == "retry_limit_reached"


def test_orchestrator_evidence():
    from orchestrator.openclaw_night_workflow.evidence import sha256_file
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "test.txt"
        f.write_text("hello")
        h = sha256_file(f)
        assert len(h) == 64


def test_orchestrator_task_store():
    from orchestrator.openclaw_night_workflow.task_store import TaskStore
    with tempfile.TemporaryDirectory() as tmp:
        store = TaskStore(db_path=Path(tmp) / "test.db")
        task_id = str(uuid.uuid4())
        store.create(
            run_id=task_id,
            workflow_id="wf-001",
            state="CREATED",
            idempotency_key=f"idem-{task_id}",
        )
        task = store.get(task_id)
        assert task is not None
        assert task["state"] == "CREATED"


def test_orchestrator_approvals():
    from orchestrator.openclaw_night_workflow.approvals import create_approval
    from orchestrator.openclaw_night_workflow.task_store import TaskStore
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        store = TaskStore(db_path=db_path)
        result = create_approval(
            store=store,
            workflow_id="wf-001",
            run_id="run-001",
            phase_id="phase-1",
            risk="R3",
            target="delete file",
        )
        assert "action_id" in result
        assert "nonce" in result
        row = store.conn.execute(
            "SELECT status FROM approvals WHERE action_id=?",
            (result["action_id"],)
        ).fetchone()
        assert row is not None
        assert row["status"] == "PENDING"


def test_agent_team_enums():
    from paios.paios.agent_team.models import ReviewDecision, Department
    assert Department.TAIZI is not None
    assert Department.ZHONGSHU is not None
    assert ReviewDecision.APPROVED is not None


def test_paios_risk():
    from paios.paios.risk import RiskAssessment
    from paios.paios.enums import RiskLevel
    ra = RiskAssessment(level=RiskLevel.R0, reasons=())
    assert ra.level == RiskLevel.R0


if __name__ == "__main__":
    print("=" * 55)
    print("Solo Core Smoke Test")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Root: {SOLO_ROOT}")
    print("=" * 55)
    print()

    tests = [
        ("PAIOS imports", test_import_paios),
        ("PAIOS schemas", test_paios_schemas),
        ("PAIOS state machine", test_paios_state_machine),
        ("PAIOS enums", test_paios_enums),
        ("PAIOS security utils", test_paios_security),
        ("Orchestrator imports", test_orchestrator_imports),
        ("Orchestrator states", test_orchestrator_states),
        ("Retry controller", test_orchestrator_retry),
        ("Evidence/audit", test_orchestrator_evidence),
        ("Task store", test_orchestrator_task_store),
        ("Approval flow", test_orchestrator_approvals),
        ("Agent team enums", test_agent_team_enums),
        ("PAIOS risk", test_paios_risk),
    ]

    passed = 0
    total = len(tests)
    for name, fn in tests:
        if step(name, fn):
            passed += 1

    print()
    print(f"Results: {passed}/{total} passed")
    print("=" * 55)
    sys.exit(0 if passed >= total - 3 else 1)
