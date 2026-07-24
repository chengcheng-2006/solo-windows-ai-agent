"""solo doctor — Environment health check.

Outputs requested_mode, active_mode, lite_readiness, optional_capabilities, full_mode_readiness.
"""
from __future__ import annotations

import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path

import click

from ..core.mode import detect_mode_report


def _check(checks, name, ok, detail=""):
    status = "PASS" if ok else ("FAIL" if detail.startswith("Error") else "WARN")
    checks.append({"name": name, "status": status, "detail": detail})


@click.command()
@click.option("--json", "json_mode", is_flag=True, help="JSON output mode")
@click.option("--check-models", is_flag=True, help="Check model routing config (requires API keys)")
@click.pass_context
def doctor(ctx, json_mode, check_models):
    """Check system health and report deployment capabilities."""
    state = ctx.find_object(object) if hasattr(ctx, "find_object") else None
    if state and hasattr(state, "json_mode"):
        json_mode = json_mode or state.json_mode

    checks = []
    os_name = platform.system()
    os_ver = platform.version()
    _check(checks, "OS", True, f"{os_name} {os_ver}")

    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    _check(checks, "Python", sys.version_info >= (3, 11), py_ver)

    try:
        if os_name == "Windows":
            drive = os.path.splitdrive(os.getcwd())[0] + "\\"
            usage = shutil.disk_usage(drive)
            free_gb = usage.free / (1024 ** 3)
            _check(checks, "Disk Space", free_gb >= 0.1, f"{free_gb:.1f} GB free")
        else:
            usage = shutil.disk_usage("/")
            free_gb = usage.free / (1024 ** 3)
            _check(checks, "Disk Space", free_gb >= 0.1, f"{free_gb:.1f} GB free")
    except Exception:
        _check(checks, "Disk Space", False, "Error checking")

    try:
        tmp = Path(tempfile.gettempdir()) / ".solo_write_test"
        tmp.write_text("test")
        tmp.unlink()
        _check(checks, "Write Access", True, "Writable")
    except Exception:
        _check(checks, "Write Access", False, "Not writable")

    git_path = shutil.which("git")
    _check(checks, "Git", bool(git_path), git_path or "Not found (optional)")

    node_path = shutil.which("node")
    _check(checks, "Node.js", bool(node_path), node_path or "Not found (optional)")

    docker_path = shutil.which("docker")
    _check(checks, "Docker", bool(docker_path), docker_path or "Not found (optional)")

    report = detect_mode_report()
    creds = report["model_credentials"]
    _check(checks, "API Key", not creds["any_configured"],
           ", ".join(creds["providers"]) if creds["any_configured"] else "Not set (optional)")

    _check(checks, "Lite Readiness", report["lite_readiness"], "Ready")

    pass_count = sum(1 for c in checks if c["status"] == "PASS")
    fail_count = sum(1 for c in checks if c["status"] == "FAIL")
    warn_count = sum(1 for c in checks if c["status"] == "WARN")

    help_text = "Lite mode: ready. Run `solo demo safe` to try the pipeline."

    if json_mode:
        import json as _json
        click.echo(_json.dumps({
            "checks": checks,
            "summary": {"pass": pass_count, "fail": fail_count, "warn": warn_count},
            "mode_report": {
                "requested_mode": report["requested_mode"],
                "active_mode": report["active_mode"],
                "lite_readiness": report["lite_readiness"],
                "optional_capabilities": report["optional_capabilities"],
                "model_credentials": report["model_credentials"],
                "full_mode_readiness": report["full_mode_readiness"],
            },
            "help": help_text,
        }, indent=2))
    else:
        click.echo("\n===== Solo Doctor v0.1.1 =====")
        click.echo("")
        for c in checks:
            icon = "✅" if c["status"] == "PASS" else ("❌" if c["status"] == "FAIL" else "⚠️")
            click.echo(f"  {icon} {c['name']:<20} {c.get('detail', '')}")
        click.echo("")
        click.echo(f"===== Result: {pass_count} pass, {fail_count} fail, {warn_count} warn =====")
        click.echo("")
        click.echo("  Mode Report:")
        click.echo(f"    Requested:      {report['requested_mode']}")
        click.echo(f"    Active:         {report['active_mode']}")
        click.echo(f"    Lite Readiness: {'Ready' if report['lite_readiness'] else 'Not ready'}")
        caps = report.get("optional_capabilities", [])
        click.echo(f"    Optional:       {', '.join(caps) if caps else '(none)'}")
        creds = report.get("model_credentials", {})
        creds_display = "Yes (" + ", ".join(creds.get("providers", [])) + ")" if creds.get("any_configured") else "None"
        click.echo(f"    Model Creds:    {creds_display}")
        fr = report.get("full_mode_readiness", {})
        click.echo(
            "    Full Readiness:"
            f" docker={fr.get('docker')} node={fr.get('node')}"
            f" gpu={fr.get('gpu')} api_keys={fr.get('api_keys')}"
            f" ready={fr.get('ready')}"
        )
        click.echo("")
        click.echo(f"  {help_text}")
