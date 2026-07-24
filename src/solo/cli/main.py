"""Solo CLI main entry point — click group with all subcommands."""
from __future__ import annotations

import sys

import click

from .. import __version__


class State:
    """Global CLI state shared across commands."""

    def __init__(self) -> None:
        self.json_mode: bool = False
        self.workspace: str = ""


pass_state = click.make_pass_decorator(State, ensure=True)


@click.group(invoke_without_command=True)
@click.option("--json", "json_mode", is_flag=True, help="JSON output mode")
@click.option("--workspace", default="", help="Custom workspace directory")
@click.pass_context
def cli(ctx: click.Context, json_mode: bool, workspace: str) -> None:
    """Solo — Personal AI agent system for Windows."""
    # Fix stdout encoding for Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[arg-type]

    state = ctx.ensure_object(State)
    state.json_mode = json_mode
    state.workspace = workspace

    if ctx.invoked_subcommand is None:
        # Default: show help
        click.echo(ctx.get_help())


@cli.command()
def version() -> None:
    """Show version and deployment mode."""
    from ..core.mode import detect_mode_str
    mode = detect_mode_str()
    click.echo(f"solo-agent v{__version__} ({mode})")


# Import and register subcommands
from .cleanup import cleanup  # noqa: E402
from .demo import demo  # noqa: E402
from .doctor import doctor  # noqa: E402
from .test_cmd import test  # noqa: E402

cli.add_command(doctor)
cli.add_command(demo)
cli.add_command(test)
cli.add_command(cleanup)
