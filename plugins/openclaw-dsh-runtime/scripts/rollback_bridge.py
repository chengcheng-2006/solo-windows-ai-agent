#!/usr/bin/env python3
"""Roll back openclaw.json to a pre-bridge backup.

The backup path must be supplied explicitly, or the helper will use the most
recent file matching `openclaw.json.pre_dsh_runtime_bridge_*` under
`~/.openclaw/backups/`.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


def default_config_path() -> Path:
    override = os.environ.get("OPENCLAW_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".openclaw" / "openclaw.json"


def find_latest_backup() -> Path | None:
    backups = sorted(
        (Path.home() / ".openclaw" / "backups").glob("openclaw.json.pre_dsh_runtime_bridge_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return backups[0] if backups else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Roll back OpenClaw config from a pre-bridge backup")
    parser.add_argument("--config", type=Path, default=default_config_path(), help="Path to openclaw.json")
    parser.add_argument("--backup", type=Path, default=None, help="Backup file to restore")
    args = parser.parse_args()

    config_path = args.config.expanduser()
    backup = args.backup.expanduser() if args.backup else find_latest_backup()
    if backup is None or not backup.exists():
        print("backup missing; pass --backup <path>", file=sys.stderr)
        sys.exit(2)

    with open(backup, "rb") as f:
        backup_data = f.read()
    with open(config_path, "rb") as f:
        current_data = f.read()

    if backup_data == current_data:
        print("config already matches backup")
        return

    shutil.copy2(config_path, config_path.with_name(config_path.name + ".rollback-previous"))
    tmp = config_path.with_name(config_path.name + ".rollback.tmp")
    with open(tmp, "wb") as f:
        f.write(backup_data)
    os.replace(tmp, config_path)
    print(f"rolled back from {backup}")


if __name__ == "__main__":
    main()
