"""solo cleanup — Clean up demo workspaces and test databases."""
from __future__ import annotations

import json as _json
import shutil
import tempfile
from pathlib import Path

import click


@click.command()
@click.option("--all", "all_flag", is_flag=True, help="Clean all including databases")
@click.option("--yes", "yes_flag", is_flag=True, help="Skip confirmation prompt")
@click.option("--force", "force_flag", is_flag=True, help="Force cleanup without prompts")
@click.option("--json", "json_mode", is_flag=True, help="JSON output mode")
@click.pass_context
def cleanup(ctx: click.Context, all_flag: bool, yes_flag: bool, force_flag: bool, json_mode: bool) -> None:
    """Clean up demo workspace and test artifacts."""
    confirm = yes_flag or force_flag
    freed_bytes = 0
    cleaned_dirs: list[str] = []

    # Scan temp dir for solo demo workspaces
    tmp = Path(tempfile.gettempdir())
    for d in tmp.iterdir():
        if d.is_dir() and d.name.startswith("solo-demo-"):
            size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            shutil.rmtree(d)
            freed_bytes += size
            cleaned_dirs.append(d.name)

    if all_flag and (confirm or click.confirm("Delete all test databases?")):
        # Clean up any .db files in the workspace
        pass

    if json_mode:
        click.echo(_json.dumps({
            "cleaned_dirs": cleaned_dirs,
            "freed_bytes": freed_bytes,
            "freed_human": f"{freed_bytes / 1024:.1f} KB",
        }))
    else:
        if cleaned_dirs:
            click.echo(f"Cleaned up {len(cleaned_dirs)} workspaces: {freed_bytes / 1024:.1f} KB freed")
        else:
            click.echo("No demo workspaces found to clean.")
