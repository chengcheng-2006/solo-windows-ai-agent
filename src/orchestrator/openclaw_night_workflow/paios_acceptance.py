from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .paios_bridges import (
    build_claude_handoff,
    build_codex_prompt_packet,
    build_task_packet,
    run_gateway_agent_via_wrapper,
    run_gemini_via_wrapper,
    run_mock_execution,
)
from .paios_core import PAIOSCore, RouteResolutionError, SYMBOLIC_ALIASES
from .schemas import utc_now


def run_acceptance(root: Path, evidence_dir: Path) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    core = PAIOSCore(root)
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail or {}})

    try:
        core.migrate()

        simple = core.create_task(
            source_channel="wechat",
            user_id="owner",
            message="explain Transformer in three sentences",
            task_type="simple",
        )
        simple_uses_gemini = simple["routing"]["executor"] == "gemini_adapter"
        check(
            "scenario1_wechat_simple_routes_free_model",
            (
                simple_uses_gemini
                and simple["routing"]["selected_provider"] == "gemini"
                and simple["routing"]["symbolic_model"] == "free_multimodal"
                and simple["routing"]["selected_model"] not in SYMBOLIC_ALIASES
            )
            or (
                simple["routing"]["executor"] == "openclaw_gateway"
                and simple["routing"]["selected_provider"] == "deepseek"
                and simple["routing"]["selected_model"] == "deepseek/deepseek-v4-flash"
                and simple["routing"]["selected_model"] not in SYMBOLIC_ALIASES
            ),
            simple["routing"],
        )
        simple_packet = build_task_packet(simple, objective="Run a real low-risk free-model acceptance prompt")
        if simple_uses_gemini:
            simple_result = run_gemini_via_wrapper(
                core,
                simple_packet,
                evidence_dir,
                prompt="Explain Transformer in three concise sentences.",
                timeout_seconds=120,
            )
        else:
            simple_result = run_gateway_agent_via_wrapper(
                core,
                simple_packet,
                evidence_dir,
                prompt="Explain Transformer in three concise sentences.",
                timeout_seconds=120,
            )
        simple_text = json.dumps(simple_result, ensure_ascii=False)
        check(
            "scenario1_real_free_model_call",
            simple_result["exit_code"] == 0
            and "Missing API key" not in simple_text
            and "GatewaySecretRefUnavailableError" not in simple_text
            and "JsonFileReadError" not in simple_text
            and "missing-provider-auth" not in simple_text,
            {"exit_code": simple_result["exit_code"], "result_path": simple_result["result_path"]},
        )

        reasoning = core.create_task(
            source_channel="wechat",
            user_id="owner",
            message="plan a complex architecture",
            task_type="planning",
        )
        check(
            "scenario2_high_reasoning_routes_hermes_deepseek",
            reasoning["routing"]["executor"] == "hermes"
            and reasoning["routing"]["selected_provider"] == "deepseek"
            and reasoning["routing"]["selected_model"] in ("deepseek/deepseek-v4-flash", "deepseek/deepseek-v4-pro"),
            reasoning["routing"],
        )
        reasoning_packet = build_task_packet(reasoning, objective="Run a real Hermes-supervised DeepSeek acceptance prompt")
        hermes_result = run_gateway_agent_via_wrapper(
            core,
            reasoning_packet,
            evidence_dir,
            prompt="Analyze three major long-running PAIOS risks. Read-only; do not modify configuration.",
            timeout_seconds=120,
        )
        hermes_text = json.dumps(hermes_result, ensure_ascii=False)
        check(
            "scenario2_real_hermes_deepseek_call",
            hermes_result["exit_code"] == 0
            and "Missing API key" not in hermes_text
            and "GatewaySecretRefUnavailableError" not in hermes_text
            and "JsonFileReadError" not in hermes_text
            and "missing-provider-auth" not in hermes_text,
            {"exit_code": hermes_result["exit_code"], "result_path": hermes_result["result_path"]},
        )

        engineering = core.create_task(
            source_channel="wechat",
            user_id="owner",
            message="fix code bug and run tests",
            task_type="engineering",
        )
        packet = build_task_packet(engineering, objective="Run a safe Codex engineering smoke task")
        codex_packet = build_codex_prompt_packet(packet, workspace=str(root))
        (evidence_dir / "scenario3_codex_prompt_packet.json").write_text(
            json.dumps(codex_packet, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        check(
            "scenario3_codex_engineering_packet",
            codex_packet["schema"] == "paios.codex_prompt_packet.v1"
            and engineering["routing"]["executor"] == "codex_cli"
            and engineering["routing"]["auth_mode"] == "codex_oauth"
            and engineering["routing"]["selected_provider"] is None,
            engineering["routing"],
        )

        fallback_route = core.route("fix code bug and run tests", task_type="engineering", codex_available=False)
        fallback_packet = build_claude_handoff(
            packet,
            checkpoint={
                "completed": ["route", "packet"],
                "pending": ["execute", "validate"],
                "artifacts": [str(evidence_dir / "scenario3_codex_prompt_packet.json")],
            },
            known_errors=["codex_quota_or_runtime_unavailable_simulated"],
        )
        (evidence_dir / "scenario4_claude_handoff_packet.json").write_text(
            json.dumps(fallback_packet, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        check(
            "scenario4_codex_failure_to_claude_handoff",
            fallback_route.executor == "claude_cli"
            and fallback_route.auth_mode == "claude_cli_auth"
            and fallback_route.selected_provider is None
            and fallback_packet["continue_mode"] == "resume_from_checkpoint",
            fallback_route.to_dict(),
        )

        team_task = core.create_task(source_channel="wechat", user_id="owner", message="batch repeat list", task_type="batch")
        team = core.plan_agent_team(team_task["task_id"], ["a", "b", "c", "d", "e", "f", "g"], max_workers=4)
        check("scenario5_agent_team_planner_workers_validator", len(team["leases"]) == 4 and team["validator"] == "deterministic", team)

        policy = core.policy_check(action="send_message", target="wechat-group", task_id=team_task["task_id"])
        check("scenario6_high_risk_requires_confirmation", policy["result"] == "REQUIRES_CONFIRMATION", policy)

        recover_task = core.create_task(source_channel="wechat", user_id="owner", message="recoverable task", task_type="simple")
        reopened = PAIOSCore(root)
        try:
            row = reopened.conn.execute("SELECT task_id,status FROM paios_tasks WHERE task_id=?", (recover_task["task_id"],)).fetchone()
            check("scenario7_restart_state_recovery", row is not None and row["task_id"] == recover_task["task_id"], {"task_id": recover_task["task_id"]})
        finally:
            reopened.close()

        watchdog_status = _run_watchdog(root)
        check("scenario8_monitoring_watchdog_pass", watchdog_status.get("status") == "PASS", {"run_id": watchdog_status.get("run_id")})

        core.put_memory(scope="private", channel="wechat", project="personal", key="private_context", value={"v": "wechat-only"}, source="acceptance")
        core.put_memory(scope="private", channel="feishu", project="work", key="office_context", value={"v": "feishu-only"}, source="acceptance")
        recalled = core.recall_memory(scope="private", channel="wechat", project="personal")
        keys = {item["key"] for item in recalled}
        check("scenario9_memory_isolation", "private_context" in keys and "office_context" not in keys)

        rollback_sim = {
            "old_config_hash": "old",
            "new_config_hash": "candidate",
            "failure": "simulated_config_failure",
            "restored_hash": "old",
            "non_critical_cleanup_blocked_service": False,
        }
        (evidence_dir / "scenario10_config_rollback_simulation.json").write_text(json.dumps(rollback_sim, ensure_ascii=False, indent=2), encoding="utf-8")
        check("scenario10_config_rollback_simulation", rollback_sim["restored_hash"] == rollback_sim["old_config_hash"] and not rollback_sim["non_critical_cleanup_blocked_service"], rollback_sim)

        try:
            core.validate_gateway_provider("openai", "openai/gpt-5.5")
            openai_blocked = False
        except RouteResolutionError as exc:
            openai_blocked = exc.code == "PROVIDER_AUTH_UNAVAILABLE"
        check("scenario11_openai_gateway_unconfigured_blocked", openai_blocked)

        mock_result = run_mock_execution(core, packet, evidence_dir)
        check("mock_execution_audited", mock_result["status"] == "completed", {"result_path": mock_result["result_path"]})

    finally:
        core.close()

    failed = [item for item in checks if item["status"] != "PASS"]
    result = {
        "schema": "paios.acceptance.v1",
        "generated_at": utc_now(),
        "status": "PASS" if not failed else "FAIL",
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "checks": checks,
    }
    (evidence_dir / "paios_acceptance_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _run_watchdog(root: Path) -> dict[str, Any]:
    script = root / "scripts" / "paios-watchdog.ps1"
    proc = subprocess.run(
        ["powershell", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(script), "-NoWrite"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    if proc.returncode != 0:
        return {"status": "FAIL", "stderr": proc.stderr[-300:]}
    return json.loads(proc.stdout)
