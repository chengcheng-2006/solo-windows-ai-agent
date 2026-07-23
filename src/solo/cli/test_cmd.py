"""solo test — Run test suite."""
from __future__ import annotations

import subprocess
import sys

import click


@click.command()
@click.option("--unit", is_flag=True, help="Run unit tests only")
@click.option("--integration", is_flag=True, help="Run integration tests")
@click.option("--coverage", is_flag=True, help="Generate coverage report")
@click.pass_context
def test(ctx: click.Context, unit: bool, integration: bool, coverage: bool) -> None:
    """Run Solo test suite."""
    import os
    solo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    cmd = [sys.executable, "-m", "pytest"]
    markers = []

    if unit:
        markers.append("lite")
    if integration:
        markers.append("core")
    if coverage:
        cmd.append("--cov=solo")
        cmd.append("--cov-report=term-missing")

    if markers:
        cmd.extend(["-m", " or ".join(markers)])

    result = subprocess.run(cmd, cwd=solo_root)
    raise SystemExit(result.returncode)
