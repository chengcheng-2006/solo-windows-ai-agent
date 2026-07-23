from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Suppress console window for subprocess calls on Windows; no-op on other platforms
_CW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


ROOT = Path(r"D:\OpenClaw-Hermes-Integration")
STATE = ROOT / "state" / "watchdog"
STATUS = STATE / "status.json"
HISTORY = STATE / "history.jsonl"
BUDGET = STATE / "restart-budget.json"
OUTBOX = STATE / "alert-outbox.jsonl"
SAFE_RESTARTS = {
    "windows_collector": ["schtasks.exe", "/Run", "/TN", "PAIOS Windows Collector"],
    "paios_core": ["powershell.exe", "-NoProfile", "-File", str(ROOT / "scripts" / "start-paios-core.ps1")],
    "temporal_worker": ["powershell.exe", "-NoProfile", "-File", str(ROOT / "scripts" / "start-temporal-worker.ps1")],
    "event_publisher": ["powershell.exe", "-NoProfile", "-File", str(ROOT / "scripts" / "start-event-publisher.ps1")],
    "executor_service": ["schtasks.exe", "/Run", "/TN", "PAIOS Executor Service"],
    "task_dispatcher": ["schtasks.exe", "/Run", "/TN", "PAIOS Task Dispatcher"],
    "ollama": ["schtasks.exe", "/Run", "/TN", "PAIOS Ollama"],
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _http(url: str) -> bool:
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=4) as response:
            return response.status == 200
    except Exception:
        return False


def _tcp(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            return True
    except OSError:
        return False


def _check(name: str, ok: bool, severity: str, reason: str = "") -> dict:
    return {"name": name, "status": "PASS" if ok else "FAIL", "severity": severity, "reason": reason if not ok else None}


def _has_forbidden_e_path(path: Path) -> bool:
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        upper = line.upper()
        if "E:\\" not in upper:
            continue
        if "STARTSWITH" in upper:
            continue
        return True
    return False


def checks() -> list[dict]:
    disk = __import__("shutil").disk_usage("D:\\")
    docker_running = bool(subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=10, creationflags=_CW).returncode == 0)
    worker_files = [
        ROOT / "workers" / "codex_worker" / "worker.py", ROOT / "workers" / "hermes_supervisor" / "supervisor.py",
        ROOT / "workers" / "browser_worker" / "worker.py", ROOT / "workers" / "windows_bridge" / "server.py",
        ROOT / "workers" / "vision_worker" / "worker.py",
        ROOT / "workers" / "executor_service" / "service.py",
        ROOT / "workers" / "task_dispatcher" / "dispatcher.py",
    ]
    return [
        _check("openclaw_gateway", _http("http://127.0.0.1:18789/health"), "critical", "Gateway health endpoint unavailable"),
        _check("d_drive_space", disk.free >= 20 * 1024**3, "critical", "D drive free space below 20 GiB"),
        _check("worker_contracts", all(path.is_file() for path in worker_files), "critical", "Required native Worker file missing"),
        _check("e_drive_policy", not any(_has_forbidden_e_path(path) for path in worker_files), "critical", "Active Worker contains non-guard E drive reference"),
        _check("docker_daemon", docker_running, "warning", "Docker daemon is stopped"),
        _check("postgres", _tcp(5432), "warning", "PostgreSQL unavailable"),
        _check("nats", _http("http://127.0.0.1:8222/healthz"), "warning", "NATS unavailable"),
        _check("temporal", _tcp(7233), "warning", "Temporal unavailable"),
        _check("paios_core", _http("http://127.0.0.1:8810/health"), "warning", "PAIOS API unavailable"),
        _check("executor_service", _http("http://127.0.0.1:8820/health"), "warning", "Native executor service unavailable"),
        _check("ollama", _http("http://127.0.0.1:11434/api/tags"), "warning", "Local Ollama service unavailable"),
        _check("task_dispatcher", (ROOT / "state" / "workers" / "task-dispatcher.json").is_file(), "warning", "Task Dispatcher heartbeat unavailable"),
        _check("prometheus", _http("http://127.0.0.1:9090/-/ready"), "warning", "Prometheus unavailable"),
        _check("loki", _http("http://127.0.0.1:3100/ready"), "warning", "Loki unavailable"),
        _check("grafana", _http("http://127.0.0.1:3000/api/health"), "warning", "Grafana unavailable"),
        _check("privacy_master", (ROOT / "secrets" / "privacy-broker-master.json").is_file(), "warning", "Owner master setup pending"),
    ]


def _load_budget() -> dict:
    if not BUDGET.exists():
        return {"schema": "paios.watchdog.restart-budget.v1", "services": {}}
    return json.loads(BUDGET.read_text(encoding="utf-8"))


def _restart(name: str, budget: dict) -> dict:
    now = time.time()
    service = budget["services"].setdefault(name, {"events": [], "consecutive_failures": 0, "circuit_open_until": 0})
    service["events"] = [event for event in service["events"] if event > now - 86400]
    if now < service["circuit_open_until"]:
        return {"attempted": False, "reason": "circuit_open"}
    if len(service["events"]) >= 3:
        service["circuit_open_until"] = now + 3600
        return {"attempted": False, "reason": "restart_budget_exhausted"}
    delay = min(2 ** service["consecutive_failures"] * 5, 300)
    if service["events"] and now - service["events"][-1] < delay:
        return {"attempted": False, "reason": "backoff", "retry_after_seconds": int(delay - (now - service["events"][-1]))}
    command = SAFE_RESTARTS.get(name)
    if not command or (command[-1].endswith(".ps1") and not Path(command[-1]).is_file()):
        return {"attempted": False, "reason": "no_safe_restart_registered"}
    completed = subprocess.run(command, capture_output=True, timeout=120, creationflags=_CW)
    service["events"].append(now)
    service["consecutive_failures"] = service["consecutive_failures"] + 1 if completed.returncode else 0
    if service["consecutive_failures"] >= 3:
        service["circuit_open_until"] = now + 3600
    return {"attempted": True, "exit_code": completed.returncode, "backoff_seconds": delay}


def _alert(check: dict, previous: dict | None) -> None:
    previous_status = (previous or {}).get(check["name"])
    current = check["status"]
    if previous_status == current:
        return
    kind = "RECOVERY" if current == "PASS" else "ALERT"
    event = {
        "schema": "paios.alert.outbox.v1", "created_at": _now(), "kind": kind,
        "component": check["name"], "severity": check["severity"], "status": current,
        "dedupe_key": hashlib.sha256(f"{check['name']}:{current}".encode()).hexdigest(),
        "cooldown_seconds": 900, "delivery": "PENDING_OPENCLAW_OWNER_ONLY",
    }
    with OUTBOX.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=True, separators=(",", ":")) + "\n")


def run(repair: bool) -> dict:
    STATE.mkdir(parents=True, exist_ok=True)
    current_checks = checks()
    previous_map = None
    if STATUS.exists():
        try:
            previous_map = {item["name"]: item["status"] for item in json.loads(STATUS.read_text(encoding="utf-8"))["checks"]}
        except Exception:
            previous_map = None
    budget = _load_budget()
    repairs = {}
    if repair:
        for item in current_checks:
            if item["status"] == "FAIL" and item["name"] in SAFE_RESTARTS:
                repairs[item["name"]] = _restart(item["name"], budget)
    critical = [item for item in current_checks if item["status"] == "FAIL" and item["severity"] == "critical"]
    warnings = [item for item in current_checks if item["status"] == "FAIL" and item["severity"] == "warning"]
    result = {
        "schema": "paios.watchdog.v2", "checked_at": _now(),
        "status": "FAIL" if critical else ("DEGRADED" if warnings else "PASS"),
        "checks": current_checks, "repairs": repairs,
        "restart_policy": {"daily_budget": 3, "backoff": "exponential", "circuit_after_failures": 3},
    }
    for item in current_checks:
        _alert(item, previous_map)
    STATUS.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    with HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=True, separators=(",", ":")) + "\n")
    BUDGET.write_text(json.dumps(budget, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()
    result = run(args.repair)
    print(json.dumps({"status": result["status"], "checks": len(result["checks"]), "repairs": result["repairs"]}, ensure_ascii=True))
    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
