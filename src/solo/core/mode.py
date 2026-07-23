"""Deployment mode detection — Lite / Core / Full.

Core principle:
- The running mode (active_mode) is ALWAYS "lite" by default.
- Optional capabilities (Docker, Node, API Keys) are reported separately.
- requested_mode reflects the SOLO_MODE env var override.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
from typing import Any

from .enums import DeploymentMode

_MODE_ENV_VAR = "SOLO_MODE"
_VALID_OVERRIDES = {"lite", "core", "full"}


def detect_mode() -> DeploymentMode:
    """Detect deployment capability, not active mode.

    Returns the highest available mode based on installed dependencies.
    This represents what the system CAN run, not what it IS running.
    Use `detect_mode_report()['active_mode']` for the active mode.
    """
    override = os.environ.get(_MODE_ENV_VAR, "").strip().lower()
    if override in _VALID_OVERRIDES:
        return DeploymentMode(override)

    has_docker = _check_docker()
    has_httpx = importlib.util.find_spec("httpx") is not None
    has_playwright = importlib.util.find_spec("playwright") is not None

    if has_docker:
        return DeploymentMode.FULL
    if has_httpx and has_playwright:
        return DeploymentMode.CORE
    return DeploymentMode.LITE


def detect_mode_str() -> str:
    """Return detected capability as string."""
    return detect_mode().value


def detect_mode_report() -> dict[str, Any]:
    """Return structured mode report for doctor and CLI output.

    Returns:
        requested_mode:  User override (env SOLO_MODE or "auto")
        active_mode:     Always "lite" — the current running mode
        lite_readiness:  Whether Lite mode can run (always true)
        optional_capabilities: List of extra tools detected
        full_mode_readiness:   Whether Full mode infra is available
    """
    override = os.environ.get(_MODE_ENV_VAR, "").strip().lower()

    has_httpx = importlib.util.find_spec("httpx") is not None
    has_playwright = importlib.util.find_spec("playwright") is not None
    has_node = shutil.which("node") is not None
    has_docker = _check_docker()
    has_api_key = bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())
    has_git = shutil.which("git") is not None

    optional_capabilities = []
    if has_httpx:
        optional_capabilities.append("httpx")
    if has_playwright:
        optional_capabilities.append("playwright")
    if has_node:
        optional_capabilities.append("node")
    if has_git:
        optional_capabilities.append("git")
    if has_api_key:
        optional_capabilities.append("api_keys")
    if has_docker:
        optional_capabilities.append("docker")

    full_mode_readiness = {
        "docker": has_docker,
        "node": has_node,
        "api_keys": has_api_key,
        "requires": ["docker", "node", "gpu", "api_keys"],
    }

    return {
        "requested_mode": override if override in _VALID_OVERRIDES else "auto",
        "active_mode": "lite",
        "lite_readiness": True,
        "optional_capabilities": optional_capabilities,
        "full_mode_readiness": full_mode_readiness,
    }


def _check_docker() -> bool:
    """Check if Docker CLI is available."""
    dockershim = importlib.util.find_spec("docker")
    if dockershim is not None:
        return True
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
