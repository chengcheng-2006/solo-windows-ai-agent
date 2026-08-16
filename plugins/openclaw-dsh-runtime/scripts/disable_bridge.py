#!/usr/bin/env python3
"""Disable the OpenClaw DSH runtime bridge and restore native DeepSeek routing."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

PLUGIN_ID = "openclaw-dsh-runtime"


def default_config_path() -> Path:
    override = os.environ.get("OPENCLAW_CONFIG")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".openclaw" / "openclaw.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Disable OpenClaw DSH runtime bridge")
    parser.add_argument("--config", type=Path, default=default_config_path(), help="Path to openclaw.json")
    args = parser.parse_args()

    config_path = args.config.expanduser()
    with open(config_path, encoding="utf-8-sig") as f:
        data = json.load(f)

    models = data["agents"]["defaults"]["models"]
    for key in ("deepseek/deepseek-v4-flash", "deepseek/deepseek-v4-pro"):
        if key in models and isinstance(models[key], dict):
            models[key]["agentRuntime"] = {"id": "openclaw"}

    data.setdefault("plugins", {}).setdefault("entries", {})[PLUGIN_ID] = {"enabled": False}

    tmp = config_path.with_name(config_path.name + ".bridge-disable.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, config_path)

    print(
        "bridge disabled: plugin enabled=false, "
        "DeepSeek model policies -> openclaw native"
    )


if __name__ == "__main__":
    main()
