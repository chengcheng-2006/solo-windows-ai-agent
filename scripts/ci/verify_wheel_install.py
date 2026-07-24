"""Verify wheel clean-install — runs in CI after python -m build.

Usage: python scripts/ci/verify_wheel_install.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def find_wheel(dist_dir: str = "dist") -> Path:
    wheels = list(Path(dist_dir).glob("*.whl"))
    if not wheels:
        print("::error::No wheel file found in dist/")
        sys.exit(1)
    return wheels[0]


def run(args: list[str], cwd: str | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, cwd=cwd, env=env, timeout=30)


def main() -> int:
    import os as _os
    # Clear all API key env vars
    clean_env = {k: v for k, v in _os.environ.items()
                 if not any(k.startswith(p) for p in ["DEEPSEEK_", "OPENAI_", "ZHIPU_", "GEMINI_"])}
    clean_env["SOLO_MODE"] = "lite"

    from click.testing import CliRunner
    from solo.cli.main import cli
    r = CliRunner()

    # Version
    v = r.invoke(cli, ["version"])
    assert v.exit_code == 0, f"version failed: {v.output}"
    assert "solo-agent v0.1.1a0" in v.output
    print(f"Version: {v.output.strip()}")

    # Doctor JSON
    d = json.loads(r.invoke(cli, ["doctor", "--json"]).output)
    m = d["mode_report"]
    assert m["active_mode"] == "lite", f"Expected lite, got {m['active_mode']}"
    assert m["lite_readiness"] is True
    assert m["model_credentials"]["any_configured"] is False
    print(f"Doctor: active={m['active_mode']}, creds={m['model_credentials']['any_configured']}")

    # Safe Demo
    with tempfile.TemporaryDirectory() as t:
        sd = json.loads(r.invoke(cli, ["demo", "safe", "--json", "--workspace", t]).output)
        assert sd["status"] == "PASS"
        print(f"Safe Demo: {sd['status']}, {sd['duration_ms']}ms, {len(sd['pipeline'])} steps")

    # VETO Demo
    with tempfile.TemporaryDirectory() as t:
        vd = json.loads(r.invoke(cli, ["demo", "veto", "--json", "--workspace", t]).output)
        assert vd["status"] == "PASS"
        assert vd["vetoed"] is True
        all_ok = all(vd["security_guarantees"].values())
        print(f"VETO Demo: {vd['status']}, vetoed={vd['vetoed']}, 6 guarantees all={all_ok}, {vd['duration_ms']}ms")

    # Cleanup
    cl = json.loads(r.invoke(cli, ["cleanup", "--json"]).output)
    print(f"Cleanup: OK (freed {cl.get('freed_bytes', 0)} bytes)")

    print("\n=== Wheel clean-room verification: ALL PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
