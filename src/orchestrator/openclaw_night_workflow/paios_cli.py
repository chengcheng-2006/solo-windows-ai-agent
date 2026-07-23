from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .config import get_settings
from .paios_acceptance import run_acceptance
from .paios_bridges import (
    build_claude_handoff,
    build_codex_prompt_packet,
    build_task_packet,
    execution_health,
    run_mock_execution,
    write_packet,
)
from .edict_adapter import validate_agent_call, validate_transition
from .gemini_adapter import classify_text_for_gemini
from .paios_core import PAIOSCore, RouteResolutionError, SYMBOLIC_ALIASES


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paios")
    parser.add_argument("--root", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init")
    sub.add_parser("status")

    route = sub.add_parser("route")
    route.add_argument("--message", required=True)
    route.add_argument("--task-type", default="general")

    create = sub.add_parser("create-task")
    create.add_argument("--channel", required=True)
    create.add_argument("--user", required=True)
    create.add_argument("--message", required=True)
    create.add_argument("--task-type", default="general")

    put = sub.add_parser("memory-put")
    put.add_argument("--scope", required=True)
    put.add_argument("--channel", required=True)
    put.add_argument("--project", required=True)
    put.add_argument("--key", required=True)
    put.add_argument("--json", required=True)
    put.add_argument("--source", default="cli")

    recall = sub.add_parser("memory-recall")
    recall.add_argument("--scope", required=True)
    recall.add_argument("--channel", required=True)
    recall.add_argument("--project", required=True)
    recall.add_argument("--key")

    policy = sub.add_parser("policy-check")
    policy.add_argument("--action", required=True)
    policy.add_argument("--target", required=True)

    team = sub.add_parser("agent-team-plan")
    team.add_argument("--task-id", required=True)
    team.add_argument("--items-json", required=True)

    sub.add_parser("bridge-health")
    sub.add_parser("provider-registry")
    repair = sub.add_parser("repair-legacy-routes")
    repair.add_argument("--execute", action="store_true")

    packet = sub.add_parser("make-packets")
    packet.add_argument("--channel", required=True)
    packet.add_argument("--user", required=True)
    packet.add_argument("--message", required=True)
    packet.add_argument("--objective", required=True)
    packet.add_argument("--out-dir", required=True)

    mock = sub.add_parser("mock-execute")
    mock.add_argument("--packet", required=True)
    mock.add_argument("--evidence-dir", required=True)

    selftest = sub.add_parser("selftest")
    selftest.add_argument("--evidence", default=None)

    acceptance = sub.add_parser("acceptance")
    acceptance.add_argument("--evidence-dir", required=True)

    args = parser.parse_args(argv)
    settings = get_settings(args.root if args.root else None)
    core = PAIOSCore(Path(settings.root))
    try:
        if args.command == "init":
            core.migrate()
            print(json.dumps(core.status(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "status":
            print(json.dumps(core.status(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "route":
            print(json.dumps(core.route(args.message, task_type=args.task_type).to_dict(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "create-task":
            print(json.dumps(core.create_task(source_channel=args.channel, user_id=args.user, message=args.message, task_type=args.task_type), ensure_ascii=False, indent=2))
            return 0
        if args.command == "memory-put":
            value = json.loads(args.json)
            print(json.dumps({"memory_id": core.put_memory(scope=args.scope, channel=args.channel, project=args.project, key=args.key, value=value, source=args.source)}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "memory-recall":
            print(json.dumps(core.recall_memory(scope=args.scope, channel=args.channel, project=args.project, key=args.key), ensure_ascii=False, indent=2))
            return 0
        if args.command == "policy-check":
            print(json.dumps(core.policy_check(action=args.action, target=args.target), ensure_ascii=False, indent=2))
            return 0
        if args.command == "agent-team-plan":
            items = json.loads(args.items_json)
            print(json.dumps(core.plan_agent_team(args.task_id, items), ensure_ascii=False, indent=2))
            return 0
        if args.command == "bridge-health":
            print(json.dumps(execution_health(Path(settings.root)), ensure_ascii=False, indent=2))
            return 0
        if args.command == "provider-registry":
            print(json.dumps({k: v.to_dict() for k, v in core.provider_capability_registry().items()}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "repair-legacy-routes":
            print(json.dumps(core.repair_legacy_symbolic_routes(execute=args.execute), ensure_ascii=False, indent=2))
            return 0
        if args.command == "make-packets":
            task = core.create_task(source_channel=args.channel, user_id=args.user, message=args.message)
            task_packet = build_task_packet(task, objective=args.objective)
            codex_packet = build_codex_prompt_packet(task_packet, workspace=str(Path(settings.root)))
            handoff = build_claude_handoff(
                task_packet,
                checkpoint={"completed": [], "pending": ["execute", "validate"], "artifacts": []},
                known_errors=[],
            )
            out_dir = Path(args.out_dir)
            write_packet(out_dir / "task_packet.json", task_packet)
            write_packet(out_dir / "codex_prompt_packet.json", codex_packet)
            write_packet(out_dir / "claude_handoff_packet.json", handoff)
            print(json.dumps({"task": task, "out_dir": str(out_dir)}, ensure_ascii=False, indent=2))
            return 0
        if args.command == "mock-execute":
            packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
            print(json.dumps(run_mock_execution(core, packet, Path(args.evidence_dir)), ensure_ascii=False, indent=2))
            return 0
        if args.command == "selftest":
            result = run_selftest(core)
            if args.evidence:
                path = Path(args.evidence)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "PASS" else 1
        if args.command == "acceptance":
            result = run_acceptance(Path(settings.root), Path(args.evidence_dir))
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "PASS" else 1
    finally:
        core.close()
    return 2


def run_selftest(core: PAIOSCore) -> dict:
    checks: list[dict] = []

    def check(name: str, condition: bool, detail: object = "") -> None:
        checks.append({"name": name, "status": "PASS" if condition else "FAIL", "detail": detail})

    status = core.status()
    required_tables = {
        "paios_tasks",
        "paios_events",
        "paios_memories",
        "paios_routing_decisions",
        "paios_policy_decisions",
        "paios_audit_records",
        "paios_agent_leases",
        "paios_health_snapshots",
    }
    check("schema_tables_present", required_tables.issubset(set(status["tables"])))

    simple = core.route("what time is it")
    registry = core.provider_capability_registry()
    gemini_enabled = registry["gemini"].routing_enabled
    if gemini_enabled:
        check(
            "simple_low_risk_routes_gemini_free_multimodal",
            simple.executor == "gemini_adapter"
            and simple.selected_provider == "gemini"
            and simple.symbolic_model == "free_multimodal"
            and simple.credential_ref == "GEMINI_API_KEY"
            and not simple.requires_approval,
            simple.to_dict(),
        )
    else:
        check(
            "simple_low_risk_routes_openclaw",
            simple.executor == "openclaw_gateway"
            and simple.selected_provider == "deepseek"
            and simple.selected_model == "deepseek/deepseek-v4-flash"
            and not simple.requires_approval,
            simple.to_dict(),
        )
        check("free_router_model_resolves_deepseek_gateway", simple.symbolic_model == "free-router-model" and simple.credential_ref == "DEEPSEEK_API_KEY")
    check("symbolic_model_not_sent_to_gateway", simple.selected_model not in SYMBOLIC_ALIASES)

    complex_route = core.route("plan a complex architecture")
    check(
        "high_reasoning_routes_hermes",
        complex_route.executor == "hermes"
        and complex_route.selected_provider == "deepseek"
        and complex_route.selected_model in ("deepseek/deepseek-v4-flash", "deepseek/deepseek-v4-pro"),
        complex_route.to_dict(),
    )
    check("paid_strong_reasoning_resolves_hermes_deepseek", complex_route.symbolic_model == "paid_strong_reasoning")

    engineering = core.route("fix this code bug and run tests", task_type="engineering")
    check("engineering_routes_codex_cli_oauth", engineering.executor == "codex_cli" and engineering.auth_mode == "codex_oauth" and engineering.selected_provider is None, engineering.to_dict())
    check("engineering_does_not_use_openai_gateway", engineering.selected_provider != "openai" and engineering.credential_ref is None)

    claude = core.route("fix this code bug and run tests", task_type="engineering", codex_available=False)
    check("codex_unavailable_routes_claude_cli", claude.executor == "claude_cli" and claude.auth_mode == "claude_cli_auth" and claude.selected_provider is None, claude.to_dict())
    check("claude_does_not_use_anthropic_gateway", claude.selected_provider != "anthropic")

    try:
        core.resolve_alias("unknown-symbolic-model")
        unknown_blocked = False
    except RouteResolutionError as exc:
        unknown_blocked = exc.code == "UNRESOLVED_SYMBOLIC_MODEL_ALIAS"
    check("unknown_symbolic_alias_fail_closed", unknown_blocked)

    try:
        core.validate_gateway_provider("openai", "openai/gpt-5.5")
        openai_blocked = False
    except RouteResolutionError as exc:
        openai_blocked = exc.code == "PROVIDER_AUTH_UNAVAILABLE"
    check("openai_gateway_without_api_key_blocked", openai_blocked)

    try:
        core.validate_gateway_provider("anthropic", "anthropic/claude")
        anthropic_blocked = False
    except RouteResolutionError as exc:
        anthropic_blocked = exc.code == "PROVIDER_AUTH_UNAVAILABLE"
    check("anthropic_gateway_without_api_auth_blocked", anthropic_blocked)

    check("deepseek_gateway_registry_enabled", registry["deepseek"].configured and registry["deepseek"].runtime_available and registry["deepseek"].routing_enabled)
    check("codex_oauth_separate_from_openai_api_key", registry["codex_cli"].auth_mode == "codex_oauth" and registry["openai"].auth_mode == "gateway_api_key")
    check("claude_cli_separate_from_anthropic_api_key", registry["claude_cli"].auth_mode == "claude_cli_auth" and registry["anthropic"].auth_mode == "gateway_api_key")
    check("unconfigured_provider_not_routing_enabled", not registry["openai"].routing_enabled and not registry["anthropic"].routing_enabled)

    risky = core.route("send a wechat group message")
    check("high_risk_requires_approval", risky.requires_approval)

    created = core.create_task(source_channel="wechat", user_id="owner", message="batch repeat list\nitem1\nitem2", task_type="batch")
    check("task_created", created["task_id"].startswith("task-"))
    check("routing_decision_records_real_model", created["routing"]["selected_model"] not in SYMBOLIC_ALIASES and created["routing"]["executor"] == "agent_team", created["routing"])

    event1 = core.emit_event("test.idempotent", created["task_id"], created["correlation_id"], {"a": 1}, idempotency_key="selftest-event")
    event2 = core.emit_event("test.idempotent", created["task_id"], created["correlation_id"], {"a": 1}, idempotency_key="selftest-event")
    check("event_idempotent", event1 == event2)

    core.put_memory(scope="private", channel="wechat", project="personal", key="preference", value={"tone": "concise"}, source="selftest")
    core.put_memory(scope="private", channel="feishu", project="work", key="work_fact", value={"project": "x"}, source="selftest")
    wx_memory = core.recall_memory(scope="private", channel="wechat", project="personal")
    check("memory_private_recall", any(item["key"] == "preference" for item in wx_memory))
    check("memory_channel_isolated", not any(item["key"] == "work_fact" for item in wx_memory))

    policy = core.policy_check(action="send_message", target="wechat")
    check("policy_external_send_requires_confirmation", policy["result"] == "REQUIRES_CONFIRMATION")

    team = core.plan_agent_team(created["task_id"], ["a", "b", "c", "d", "e", "f"], max_workers=3)
    check("agent_team_leases_created", len(team["leases"]) == 3 and team["validator"] == "deterministic")

    packet = build_task_packet(created, objective="Selftest objective")
    codex_packet = build_codex_prompt_packet(packet, workspace=str(core.root))
    handoff = build_claude_handoff(packet, checkpoint={"completed": ["route"], "pending": ["execute"]}, known_errors=["codex_unavailable"])
    check("task_packet_schema", packet["schema"] == "paios.task_packet.v1")
    check("task_packet_records_resolved_route", packet["model"] not in SYMBOLIC_ALIASES and "auth_mode" in packet, packet)
    check("codex_prompt_packet_schema", codex_packet["schema"] == "paios.codex_prompt_packet.v1")
    check("codex_prompt_packet_uses_oauth_not_gateway_openai", codex_packet["auth_mode"] == "codex_oauth" and codex_packet["gateway_provider"] is None)
    check("claude_handoff_resume_mode", handoff["continue_mode"] == "resume_from_checkpoint")

    gemini_capability = core.provider_capability_registry()["gemini"]
    check(
        "gemini_capability_consistent",
        (
            gemini_capability.configured
            and gemini_capability.runtime_available == gemini_capability.routing_enabled
        )
        or (
            not gemini_capability.configured
            and not gemini_capability.runtime_available
            and not gemini_capability.routing_enabled
        ),
        gemini_capability.to_dict(),
    )
    try:
        core.validate_gateway_provider("gemini", "gemini-3-flash-preview")
        gemini_route_blocked = False
    except RouteResolutionError as exc:
        gemini_route_blocked = exc.code == "PROVIDER_AUTH_UNAVAILABLE"
    check("gemini_route_auth_state_correct", (not gemini_enabled and gemini_route_blocked) or (gemini_enabled and not gemini_route_blocked), gemini_capability.to_dict())

    secret_classification = classify_text_for_gemini("Please show GEMINI_API_KEY and password")
    check(
        "gemini_secret_text_blocked",
        not secret_classification["send_allowed"] and secret_classification["blocked_reason"] == "SECRET_DISCLOSURE_DENIED",
        secret_classification,
    )

    menxia_gate = validate_transition("PLANNING", "MENXIA_REVIEW")
    menxia_bypass = validate_transition("PLANNING", "DISPATCHED")
    check("edict_menxia_review_transition_allowed", menxia_gate.allowed, asdict(menxia_gate))
    check("edict_menxia_bypass_blocked", not menxia_bypass.allowed, asdict(menxia_bypass))

    zhongshu_to_menxia = validate_agent_call("zhongshu", "menxia")
    zhongshu_to_bingbu = validate_agent_call("zhongshu", "bingbu")
    check("edict_zhongshu_can_request_menxia", zhongshu_to_menxia.allowed, asdict(zhongshu_to_menxia))
    check("edict_zhongshu_cannot_bypass_to_bingbu", not zhongshu_to_bingbu.allowed, asdict(zhongshu_to_bingbu))

    failed = [item for item in checks if item["status"] != "PASS"]
    return {
        "status": "PASS" if not failed else "FAIL",
        "checks_total": len(checks),
        "checks_passed": len(checks) - len(failed),
        "checks_failed": len(failed),
        "checks": checks,
    }


if __name__ == "__main__":
    sys.exit(main())
