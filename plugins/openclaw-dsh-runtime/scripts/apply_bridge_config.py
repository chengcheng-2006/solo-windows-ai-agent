#!/usr/bin/env python3
"""Apply the openclaw-dsh-runtime model policy and plugin configuration.

This helper is idempotent. It edits the OpenClaw JSON configuration only; it
never writes credentials, runtime state, or DSH session data.
"""
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


def default_plugin_path() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply OpenClaw DSH runtime bridge config")
    parser.add_argument("--config", type=Path, default=default_config_path(), help="Path to openclaw.json")
    parser.add_argument("--plugin-path", type=Path, default=default_plugin_path(), help="Path to openclaw-dsh-runtime plugin directory")
    args = parser.parse_args()

    config_path = args.config.expanduser()
    plugin_path = str(args.plugin_path.expanduser().resolve())

    with open(config_path, encoding="utf-8-sig") as f:
        data = json.load(f)

    models = data["agents"]["defaults"]["models"]
    models["deepseek/deepseek-v4-flash"] = {
        **models.get("deepseek/deepseek-v4-flash", {}),
        "agentRuntime": {"id": "dsh-flash-router"},
    }
    models["deepseek/deepseek-v4-pro"] = {
        **models.get("deepseek/deepseek-v4-pro", {}),
        "agentRuntime": {"id": "dsh-pro-anchored"},
    }

    plugins = data.setdefault("plugins", {})
    load = plugins.setdefault("load", {})
    paths = load.setdefault("paths", [])
    if plugin_path not in paths:
        paths.append(plugin_path)

    allow = plugins.setdefault("allow", [])
    if PLUGIN_ID not in allow:
        allow.append(PLUGIN_ID)

    entries = plugins.setdefault("entries", {})
    entries.setdefault(PLUGIN_ID, {})["enabled"] = True

    tmp = config_path.with_name(config_path.name + ".bridge-apply.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, config_path)

    print(
        "applied: openclaw-dsh-runtime enabled; "
        "Flash->dsh-flash-router; Pro->dsh-pro-anchored"
    )


if __name__ == "__main__":
    main()
