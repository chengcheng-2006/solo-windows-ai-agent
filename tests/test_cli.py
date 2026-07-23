"""Tests for CLI commands using Click CliRunner."""
import json
import pytest
from click.testing import CliRunner

from solo.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Solo" in result.output


def test_version(runner):
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert "solo-agent v" in result.output
    # Accept any mode: lite, core, or full (depending on environment)
    assert any(m in result.output for m in ("lite", "core", "full"))


def test_doctor(runner):
    result = runner.invoke(cli, ["doctor"])
    assert result.exit_code == 0
    assert "Python" in result.output or "Result" in result.output


def test_doctor_json(runner):
    result = runner.invoke(cli, ["doctor", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "checks" in data
    assert "summary" in data
    assert "mode_report" in data
    assert data["mode_report"]["active_mode"] == "lite"
    assert data["mode_report"]["lite_readiness"] is True
    assert data["summary"]["pass"] >= 0


def test_demo_safe(runner, tmp_path):
    result = runner.invoke(cli, ["demo", "safe", "--workspace", str(tmp_path)])
    assert result.exit_code == 0
    assert "SUCCESS" in result.output or "Demo" in result.output


def test_demo_safe_json(runner, tmp_path):
    result = runner.invoke(cli, ["demo", "safe", "--json", "--workspace", str(tmp_path)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "PASS"
    assert data["mode"] == "lite"
    assert len(data["pipeline"]) == 8


def test_demo_veto(runner, tmp_path):
    result = runner.invoke(cli, ["demo", "veto", "--workspace", str(tmp_path)])
    assert result.exit_code == 0
    assert "SUCCESS" in result.output or "VETO" in result.output


def test_demo_veto_json(runner, tmp_path):
    result = runner.invoke(cli, ["demo", "veto", "--json", "--workspace", str(tmp_path)])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "PASS"
    assert data["vetoed"] is True
    assert data["risk_level"] == "R3"
    # Check all 6 security guarantees
    for key, val in data["security_guarantees"].items():
        assert val is True, f"Guarantee '{key}' failed: {val}"


def test_cleanup(runner):
    result = runner.invoke(cli, ["cleanup"])
    assert result.exit_code == 0


def test_demo_safe_creates_files(runner, tmp_path):
    runner.invoke(cli, ["demo", "safe", "--workspace", str(tmp_path)])
    assert (tmp_path / "sample_text.txt").exists()
    assert (tmp_path / "demo.db").exists()


def test_demo_veto_creates_db(runner, tmp_path):
    runner.invoke(cli, ["demo", "veto", "--workspace", str(tmp_path)])
    assert (tmp_path / "demo.db").exists()
