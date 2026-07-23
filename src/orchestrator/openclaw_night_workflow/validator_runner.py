from __future__ import annotations

import json
import uuid
from pathlib import Path

from .redaction import contains_secret
from .schemas import ValidationResult


PHASE_REQUIRED = {
    "bootstrap-entry": [
        "evidence/00_5_skill_info_final.json",
        "evidence/00_5_plugin_inspect_final.json",
        "evidence/00_5_explicit_skill_status_test.json",
        "evidence/00_5_natural_language_status_test.json",
        "evidence/00_5_dry_run_start_test.json",
        "evidence/00_5_security_tests.json",
        "evidence/00_5_database_phase_start_check.json",
    ],
    "phase1": ["audit/OPENCLAW_BASELINE.md", "evidence/01_audit_summary.json", "prompts/source/CHECKSUMS.sha256"],
    "phase2": ["docs/PHASE2_INSTALLATION_REPORT.md", "evidence/02_phase_summary.json", "database/night_workflows.db"],
    "phase3": ["docs/V1_DEPLOYMENT_REPORT.md", "evidence/03_final_summary.json", "scripts/rollback_phase3.ps1"],
}


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _read_json(path: Path) -> dict:
    return json.loads(_read_text(path))


def _agent_result_has_tool(path: Path, tool_name: str) -> bool:
    data = _read_json(path)
    if data.get("status") != "ok":
        return False
    meta = data.get("result", {}).get("meta", {})
    tool_summary = meta.get("toolSummary", {})
    tool_names = set(tool_summary.get("tools", []))
    prompt_tools = {
        entry.get("name")
        for entry in meta.get("systemPromptReport", {}).get("tools", {}).get("entries", [])
        if isinstance(entry, dict)
    }
    return tool_name in tool_names and tool_name in prompt_tools and int(tool_summary.get("failures", 0)) == 0


def _validate_bootstrap_entry(root: Path, workflow_id: str, run_id: str, required: list[str]) -> ValidationResult:
    missing = [path for path in required if not (root / path).exists()]
    failures: list[str] = []
    evidence = [path for path in required if (root / path).exists()]

    def require(condition: bool, code: str) -> None:
        if not condition:
            failures.append(code)

    if not missing:
        skill_info = _read_json(root / "evidence/00_5_skill_info_final.json")
        require(skill_info.get("name") == "openclaw-hermes-v1", "skill_name_mismatch")
        require(skill_info.get("eligible") is True, "skill_not_eligible")
        require(skill_info.get("modelVisible") is True, "skill_not_model_visible")
        require(skill_info.get("userInvocable") is True, "skill_not_user_invocable")
        require(skill_info.get("commandVisible") is True, "skill_not_command_visible")

        plugin = _read_json(root / "evidence/00_5_plugin_inspect_final.json").get("plugin", {})
        require(plugin.get("id") == "openclaw-night-workflow", "plugin_id_mismatch")
        require(plugin.get("enabled") is True and plugin.get("activated") is True, "plugin_not_enabled_or_activated")
        require(plugin.get("status") == "loaded", "plugin_not_loaded")
        require("night_workflow_control" in plugin.get("toolNames", []), "tool_not_registered")
        require("night_workflow_control" in plugin.get("contracts", {}).get("tools", []), "tool_contract_missing")

        require(_agent_result_has_tool(root / "evidence/00_5_explicit_skill_status_test.json", "night_workflow_control"), "explicit_skill_status_not_tool_backed")
        require(_agent_result_has_tool(root / "evidence/00_5_natural_language_status_test.json", "night_workflow_control"), "natural_language_status_not_tool_backed")
        require(_agent_result_has_tool(root / "evidence/00_5_dry_run_start_test.json", "night_workflow_control"), "dry_run_start_not_tool_backed")

        security = _read_json(root / "evidence/00_5_security_tests.json").get("summary", {})
        require(security.get("failed") == 0, "security_tests_failed")
        require(security.get("non_owner_start_blocked") is True, "non_owner_start_not_blocked")
        require(security.get("injection_tests_passed") is True, "injection_tests_failed")
        require(security.get("real_start_blocked") is True, "real_start_not_blocked")
        require(security.get("formal_phase_started_in_positive_start_tests") is False, "formal_phase_started_during_positive_tests")

        database = _read_json(root / "evidence/00_5_database_phase_start_check.json")
        require(database.get("formal_phase_started") is False, "database_indicates_formal_phase_started")
        require(database.get("execution_attempts_count") == 0, "execution_attempts_exist")
        require(database.get("phase_runs_count") == 0, "phase_runs_exist")

    checks_total = len(required) + 21
    checks_failed = len(missing) + len(failures)
    result = "PASS" if checks_failed == 0 else "BLOCKED"
    return ValidationResult(
        workflow_id=workflow_id,
        run_id=run_id,
        phase_id="bootstrap-entry",
        validation_id=f"val-{uuid.uuid4().hex[:12]}",
        result=result,
        checks_total=checks_total,
        checks_passed=checks_total - checks_failed,
        checks_failed=checks_failed,
        critical_failures=[] if result == "PASS" else failures or ["bootstrap_entry_evidence_missing"],
        security_findings=[],
        missing_artifacts=missing,
        retryable_findings=missing + failures,
        requires_user_action=False,
        recommended_next_state="COMPLETED" if result == "PASS" else "WAITING_FOR_USER",
        evidence=evidence,
    )


def validate_phase(root: Path, workflow_id: str, run_id: str, phase_id: str) -> ValidationResult:
    required = PHASE_REQUIRED.get(phase_id, [])
    if phase_id == "bootstrap-entry":
        return _validate_bootstrap_entry(root, workflow_id, run_id, required)
    missing = [path for path in required if not (root / path).exists()]
    evidence = [path for path in required if (root / path).exists()]
    security_findings: list[str] = []
    for rel in evidence:
        path = root / rel
        if path.is_file() and contains_secret(path.read_text(encoding="utf-8", errors="ignore")):
            security_findings.append(f"secret_pattern_detected:{rel}")
    checks_total = len(required) + 1
    checks_failed = len(missing) + len(security_findings)
    result = "PASS" if checks_failed == 0 else "BLOCKED"
    return ValidationResult(
        workflow_id=workflow_id,
        run_id=run_id,
        phase_id=phase_id,
        validation_id=f"val-{uuid.uuid4().hex[:12]}",
        result=result,
        checks_total=checks_total,
        checks_passed=checks_total - checks_failed,
        checks_failed=checks_failed,
        critical_failures=[] if result == "PASS" else ["required_phase_evidence_missing"],
        security_findings=security_findings,
        missing_artifacts=missing,
        retryable_findings=missing,
        requires_user_action=False,
        recommended_next_state="COMPLETED" if result == "PASS" else "WAITING_FOR_USER",
        evidence=evidence,
    )


def write_validation_result(path: Path, result: ValidationResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
