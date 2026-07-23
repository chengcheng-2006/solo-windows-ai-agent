from __future__ import annotations

import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from .paios_core import PAIOSCore
from .redaction import redact
from .schemas import utc_now


OPENCLAW_CLI_WRAPPER = Path(r"D:\OpenClaw-Hermes-Integration\orchestrator\scripts\openclaw-cli-protected.ps1")
GEMINI_PROMPT_WRAPPER = Path(r"D:\OpenClaw-Hermes-Integration\orchestrator\scripts\run_gemini_dpapi_prompt.ps1")
APPROVED_WRAPPER_ROOTS = (
    Path(r"D:\OpenClaw-Hermes-Integration"),
    Path(r"D:\OpenClaw-Hermes-Backups"),
)


def build_task_packet(task: dict[str, Any], *, objective: str, constraints: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema": "paios.task_packet.v1",
        "task_id": task["task_id"],
        "correlation_id": task["correlation_id"],
        "objective": objective,
        "constraints": constraints or [],
        "risk": task["routing"]["risk"],
        "executor": task["routing"]["executor"],
        "model": task["routing"]["selected_model"],
        "provider": task["routing"].get("selected_provider"),
        "symbolic_model": task["routing"].get("symbolic_model"),
        "auth_mode": task["routing"].get("auth_mode"),
        "credential_ref": task["routing"].get("credential_ref"),
        "created_at": utc_now(),
    }


def build_codex_prompt_packet(packet: dict[str, Any], *, workspace: str) -> dict[str, Any]:
    return {
        "schema": "paios.codex_prompt_packet.v1",
        "task_id": packet["task_id"],
        "workspace": workspace,
        "objective": packet["objective"],
        "constraints": packet["constraints"],
        "auth_mode": "codex_oauth",
        "gateway_provider": None,
        "required_evidence": ["commands", "changed_files", "test_results", "summary"],
        "safety": {
            "no_secret_output": True,
            "no_e_drive_write": True,
            "confirm_external_messages": True,
        },
    }


def build_claude_handoff(packet: dict[str, Any], *, checkpoint: dict[str, Any], known_errors: list[str]) -> dict[str, Any]:
    return {
        "schema": "paios.claude_handoff.v1",
        "task_id": packet["task_id"],
        "correlation_id": packet["correlation_id"],
        "objective": packet["objective"],
        "completed": checkpoint.get("completed", []),
        "pending": checkpoint.get("pending", []),
        "artifacts": checkpoint.get("artifacts", []),
        "known_errors": known_errors,
        "continue_mode": "resume_from_checkpoint",
        "created_at": utc_now(),
    }


def execution_health(root: Path) -> dict[str, Any]:
    supervisor = root / "workers" / "hermes_supervisor" / "supervisor.py"
    launcher = root / "scripts" / "hermes-supervisor-protected.ps1"
    vault = root / "secrets" / "hermes-dpapi-store.json"
    legacy_env = root / "data" / "hermes" / ".env"
    plaintext_assignments = 0
    if legacy_env.is_file():
        for line in legacy_env.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith(("ANTHROPIC_API_KEY=", "OPENAI_API_KEY=")):
                plaintext_assignments += 1
    hermes_ok = all(path.is_file() for path in (supervisor, launcher, vault)) and plaintext_assignments == 0
    return {
        "codex": _cli_health("codex", ["--version"]),
        "claude_code": _cli_health("claude", ["--version"]),
        "hermes_supervisor": {
            "status": "PASS" if hermes_ok else "FAIL",
            "transport": "ACP_STDIN",
            "supervisor": str(supervisor),
            "launcher": str(launcher),
            "secret_store": str(vault),
            "plaintext_secret_assignments": plaintext_assignments,
        },
    }


def run_mock_execution(core: PAIOSCore, packet: dict[str, Any], evidence_dir: Path) -> dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "schema": "paios.mock_execution_result.v1",
        "task_id": packet["task_id"],
        "executor": packet["executor"],
        "status": "completed",
        "summary": "Mock execution completed without external side effects.",
        "created_at": utc_now(),
    }
    result_path = evidence_dir / f"{packet['task_id']}_mock_execution.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    core.emit_event("task.completed", packet["task_id"], packet["correlation_id"], {"result_path": str(result_path)})
    core.audit(
        task_id=packet["task_id"],
        actor="paios-mock-executor",
        channel="internal",
        action="execute.mock",
        tool="paios_bridges",
        result="completed",
        files=[str(result_path)],
    )
    return {**result, "result_path": str(result_path)}


def run_gateway_agent_via_wrapper(
    core: PAIOSCore,
    packet: dict[str, Any],
    evidence_dir: Path,
    *,
    prompt: str,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    if packet.get("executor") not in ("openclaw_gateway", "hermes"):
        raise ValueError("Gateway wrapper is only approved for OpenClaw Gateway or Hermes-supervised DeepSeek routes.")
    provider = packet.get("provider")
    model = packet.get("model")
    if provider != "deepseek" or model not in ("deepseek/deepseek-v4-flash", "deepseek/deepseek-v4-pro"):
        raise ValueError("Gateway wrapper route must resolve to an approved DeepSeek Gateway model.")
    evidence_dir = _assert_approved_path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = _assert_approved_path(evidence_dir / f"{packet['task_id']}_gateway_prompt.txt")
    prompt_path.write_text(prompt, encoding="utf-8")

    started = time.monotonic()
    cmd = [
        "powershell",
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(OPENCLAW_CLI_WRAPPER),
        "-Operation",
        "AgentRun",
        "-PromptFile",
        str(prompt_path),
        "-TimeoutSeconds",
        str(timeout_seconds),
        "-WorkingDirectory",
        str(evidence_dir.parent),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_seconds + 30)
    duration_ms = int((time.monotonic() - started) * 1000)
    stdout = redact(proc.stdout or "")
    stderr = redact(proc.stderr or "")
    wrapper_payload: dict[str, Any] | None = None
    if stdout.strip():
        try:
            wrapper_payload = json.loads(stdout)
            if isinstance(wrapper_payload, dict):
                wrapper_payload["stdout"] = redact(str(wrapper_payload.get("stdout", "")))
                wrapper_payload["stderr"] = redact(str(wrapper_payload.get("stderr", "")))
        except json.JSONDecodeError:
            wrapper_payload = None

    result = {
        "schema": "paios.gateway_wrapper_result.v1",
        "task_id": packet["task_id"],
        "correlation_id": packet["correlation_id"],
        "executor": packet.get("executor"),
        "provider": provider,
        "model": model,
        "wrapper": str(OPENCLAW_CLI_WRAPPER),
        "exit_code": proc.returncode,
        "duration_ms": duration_ms,
        "stdout": stdout,
        "stderr": stderr,
        "wrapper_payload": wrapper_payload,
        "prompt_file": str(prompt_path),
        "created_at": utc_now(),
    }
    result_path = evidence_dir / f"{packet['task_id']}_gateway_wrapper_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    core.emit_event(
        "task.gateway_wrapper.completed" if proc.returncode == 0 else "task.gateway_wrapper.failed",
        packet["task_id"],
        packet["correlation_id"],
        {"result_path": str(result_path), "exit_code": proc.returncode, "duration_ms": duration_ms},
    )
    core.audit(
        task_id=packet["task_id"],
        actor="paios-gateway-wrapper",
        channel="internal",
        action="execute.gateway_agent",
        tool="openclaw-cli-protected.ps1",
        model=model,
        result="completed" if proc.returncode == 0 else "failed",
        files=[str(result_path)],
        command_summary="OpenClaw protected CLI wrapper AgentRun",
    )
    return {**result, "result_path": str(result_path)}


def run_gemini_via_wrapper(
    core: PAIOSCore,
    packet: dict[str, Any],
    evidence_dir: Path,
    *,
    prompt: str,
    timeout_seconds: int = 90,
) -> dict[str, Any]:
    if packet.get("executor") != "gemini_adapter" or packet.get("provider") != "gemini":
        raise ValueError("Gemini wrapper is only approved for resolved Gemini adapter routes.")
    evidence_dir = _assert_approved_path(evidence_dir)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = _assert_approved_path(evidence_dir / f"{packet['task_id']}_gemini_prompt.txt")
    prompt_path.write_text(prompt, encoding="utf-8")

    started = time.monotonic()
    cmd = [
        "powershell",
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(GEMINI_PROMPT_WRAPPER),
        "-PromptFile",
        str(prompt_path),
        "-EvidenceDir",
        str(evidence_dir),
        "-Model",
        str(packet.get("model") or ""),
        "-TimeoutSeconds",
        str(timeout_seconds),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_seconds + 30)
    duration_ms = int((time.monotonic() - started) * 1000)
    stdout = redact(proc.stdout or "")
    stderr = redact(proc.stderr or "")
    wrapper_payload: dict[str, Any] | None = None
    if stdout.strip():
        try:
            wrapper_payload = json.loads(stdout)
        except json.JSONDecodeError:
            wrapper_payload = None

    result = {
        "schema": "paios.gemini_wrapper_result.v1",
        "task_id": packet["task_id"],
        "correlation_id": packet["correlation_id"],
        "executor": packet.get("executor"),
        "provider": packet.get("provider"),
        "model": packet.get("model"),
        "wrapper": str(GEMINI_PROMPT_WRAPPER),
        "exit_code": proc.returncode,
        "duration_ms": duration_ms,
        "stdout": stdout,
        "stderr": stderr,
        "wrapper_payload": wrapper_payload,
        "prompt_file": str(prompt_path),
        "created_at": utc_now(),
    }
    result_path = evidence_dir / f"{packet['task_id']}_gemini_wrapper_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    core.emit_event(
        "task.gemini_wrapper.completed" if proc.returncode == 0 else "task.gemini_wrapper.failed",
        packet["task_id"],
        packet["correlation_id"],
        {"result_path": str(result_path), "exit_code": proc.returncode, "duration_ms": duration_ms},
    )
    core.audit(
        task_id=packet["task_id"],
        actor="paios-gemini-wrapper",
        channel="internal",
        action="execute.gemini_adapter",
        tool="run_gemini_dpapi_prompt.ps1",
        model=packet.get("model"),
        result="completed" if proc.returncode == 0 else "failed",
        files=[str(result_path)],
        command_summary="Gemini DPAPI child-env prompt wrapper",
    )
    return {**result, "result_path": str(result_path)}


def write_packet(path: Path, packet: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")


def _assert_approved_path(path: Path) -> Path:
    resolved = path.resolve()
    if str(resolved).upper().startswith("E:\\"):
        raise ValueError("E: drive paths are not allowed.")
    for root in APPROVED_WRAPPER_ROOTS:
        root_resolved = root.resolve()
        try:
            resolved.relative_to(root_resolved)
            return resolved
        except ValueError:
            continue
    raise ValueError("Path is outside approved PAIOS roots.")


def _cli_health(name: str, args: list[str]) -> dict[str, Any]:
    exe = shutil.which(name)
    if not exe:
        return {"status": "FAIL", "reason": f"{name} not found"}
    try:
        proc = subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
    except Exception as exc:  # pragma: no cover - platform specific
        return {"status": "FAIL", "path": exe, "reason": str(exc)}
    output = redact((proc.stdout or proc.stderr or "").strip())
    return {"status": "PASS" if proc.returncode == 0 else "FAIL", "path": exe, "exit_code": proc.returncode, "output": output[:300]}
