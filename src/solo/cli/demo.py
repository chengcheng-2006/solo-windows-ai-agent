"""solo demo — Demo subcommand group (safe, veto)."""
from __future__ import annotations

import json as _json
import tempfile
import time
from pathlib import Path

import click

from ..demo.formatter import format_demo_human, format_demo_json
from ..demo.safe_demo import run_safe_demo
from ..demo.veto_demo import run_veto_demo, R3_HAZARDOUS_REQUEST


@click.group()
def demo() -> None:
    """Run Solo demo pipelines."""


@demo.command()
@click.option("--workspace", default="", help="Custom workspace directory")
@click.option("--json", "json_mode", is_flag=True, help="JSON output mode")
@click.pass_context
def safe(ctx: click.Context, workspace: str, json_mode: bool) -> None:
    """Run Safe Demo: R0 task end-to-end pipeline."""
    ws = _resolve_workspace(workspace, "solo-demo-safe")
    ws.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()
    result = run_safe_demo(ws)
    elapsed = (time.monotonic() - start) * 1000
    result["duration_ms"] = round(elapsed, 1)

    if json_mode:
        click.echo(format_demo_json(result))
    else:
        click.echo(format_demo_human(result, "Solo Safe Demo"))
        click.echo(f"Workspace: {ws}")
        click.echo(f"Duration: {elapsed:.0f}ms")

    if result.get("status") != "PASS":
        raise SystemExit(1)


@demo.command()
@click.option("--workspace", default="", help="Custom workspace directory")
@click.option("--json", "json_mode", is_flag=True, help="JSON output mode")
@click.pass_context
def veto(ctx: click.Context, workspace: str, json_mode: bool) -> None:
    """Run VETO Demo: R3 high-risk request rejected."""
    ws = _resolve_workspace(workspace, "solo-demo-veto")
    ws.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()
    result = run_veto_demo(ws)
    elapsed = (time.monotonic() - start) * 1000
    result["duration_ms"] = round(elapsed, 1)

    if json_mode:
        click.echo(format_demo_json(result))
    else:
        click.echo(format_demo_human(result, "Solo VETO Demo"))
        click.echo(f"Workspace: {ws}")
        click.echo(f"Duration: {elapsed:.0f}ms")
        click.echo(f'Hazardous Request: "{R3_HAZARDOUS_REQUEST}"')

    if result.get("status") != "PASS":
        raise SystemExit(1)


def _resolve_workspace(ws: str, prefix: str) -> Path:
    """Resolve workspace path from user input or create temp dir."""
    if ws:
        return Path(ws).resolve()
    return Path(tempfile.mkdtemp(prefix=prefix))
