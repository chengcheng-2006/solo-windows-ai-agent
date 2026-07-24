"""Tests for VETO Demo — R3 rejected pipeline with security guarantees."""

from solo.demo.veto_demo import run_veto_demo


def test_veto_demo_runs_successfully(tmp_path):
    result = run_veto_demo(tmp_path)
    assert result["status"] == "PASS"
    assert result["vetoed"] is True
    assert result["risk_level"] == "R3"


def test_veto_demo_has_4_steps(tmp_path):
    result = run_veto_demo(tmp_path)
    pipeline = result["pipeline"]
    assert len(pipeline) == 4
    states = [e["state"] for e in pipeline]
    assert states == ["RECEIVED", "TRIAGED", "REVIEW_PENDING", "REJECTED"]


def test_veto_demo_security_guarantees_all_pass(tmp_path):
    result = run_veto_demo(tmp_path)
    guarantees = result["security_guarantees"]
    for key, val in guarantees.items():
        assert val is True, f"Security guarantee '{key}' failed"


def test_veto_demo_six_guarantees(tmp_path):
    result = run_veto_demo(tmp_path)
    guarantees = result["security_guarantees"]
    assert len(guarantees) == 6
    expected_keys = {
        "R3_correctly_classified",
        "step_level_approval_required",
        "approval_rejected_by_reviewer",
        "state_is_terminal",
        "no_execution_occurred",
        "approval_nonce_consumed",
    }
    assert set(guarantees.keys()) == expected_keys


def test_veto_demo_no_execution(tmp_path):
    """Verify VETO demo has zero execution attempts."""
    import sqlite3

    run_veto_demo(tmp_path)
    conn = sqlite3.connect(str(tmp_path / "demo.db"))
    count = conn.execute(
        "SELECT COUNT(*) as c FROM execution_attempts"
    ).fetchone()[0]
    conn.close()
    assert count == 0, f"Expected 0 execution attempts, got {count}"


def test_veto_demo_approval_rejected(tmp_path):
    import sqlite3

    run_veto_demo(tmp_path)
    conn = sqlite3.connect(str(tmp_path / "demo.db"))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT status FROM approvals"
    ).fetchall()
    conn.close()
    for row in rows:
        assert row["status"] == "REJECTED", f"Expected REJECTED, got {row['status']}"


def test_veto_demo_no_api_keys(tmp_path):
    """Verify VETO demo does not require API keys."""
    result = run_veto_demo(tmp_path)
    assert result["status"] == "PASS"


def test_veto_demo_r3_reasons(tmp_path):
    result = run_veto_demo(tmp_path)
    assert len(result["risk_reasons"]) > 0
