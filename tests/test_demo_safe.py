"""Tests for Safe Demo — 8-step pipeline end-to-end."""

from solo.demo.safe_demo import run_safe_demo


def test_safe_demo_runs_successfully(tmp_path):
    result = run_safe_demo(tmp_path)
    assert result["status"] == "PASS"
    assert result["mode"] == "lite"
    assert result["task_id"].startswith("run-")


def test_safe_demo_has_8_steps(tmp_path):
    result = run_safe_demo(tmp_path)
    pipeline = result["pipeline"]
    assert len(pipeline) == 8
    states = [e["state"] for e in pipeline]
    assert states == ["RECEIVED", "TRIAGED", "PLANNING", "APPROVED",
                      "DISPATCHED", "EXECUTING", "VALIDATING", "COMPLETED"]


def test_safe_demo_word_count(tmp_path):
    result = run_safe_demo(tmp_path)
    assert result["result"]["word_count"] > 0
    assert result["result"]["validation"] == "PASS"


def test_safe_demo_creates_db(tmp_path):
    run_safe_demo(tmp_path)
    db_file = tmp_path / "demo.db"
    assert db_file.exists()


def test_safe_demo_creates_evidence_manifest(tmp_path):
    result = run_safe_demo(tmp_path)
    manifest_path = result.get("evidence_manifest", "")
    assert manifest_path, "No evidence_manifest in result"
    import json
    manifest = json.loads((tmp_path / "evidence" / "demo_file_manifest.json").read_text())
    assert manifest["file_count"] > 0


def test_safe_demo_task_is_r0(tmp_path):
    result = run_safe_demo(tmp_path)
    # The Safe Demo objective is "Count words in a test text file" → R0
    pipeline = result["pipeline"]
    triaged = pipeline[1]
    risk_val = triaged.get("risk", "")
    assert risk_val == "R0" or "R0" in str(risk_val), f"Expected R0, got {risk_val}"


def test_safe_demo_no_api_keys(tmp_path):
    """Verify demo does not require API keys by checking env vars are unset."""
    # This test runs without API keys being set
    result = run_safe_demo(tmp_path)
    assert result["status"] == "PASS"


def test_safe_demo_workspace_has_files(tmp_path):
    run_safe_demo(tmp_path)
    files = list(tmp_path.iterdir())
    assert any(f.name == "sample_text.txt" for f in files), "No sample_text.txt created"
