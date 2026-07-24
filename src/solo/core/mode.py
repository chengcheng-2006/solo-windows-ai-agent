"""Deployment mode detection — Lite / Core / Full.

Core principle:
- requested_mode reflects the SOLO_MODE env var override or "auto".
- active_mode reflects what is actually active after capability checks.
- Full mode requires Docker + Node + GPU + API keys to be considered ready.
- Docker CLI alone does NOT activate Full mode.
- Placeholder values (YOUR_*, CHANGE_ME) are NOT valid credentials.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
from typing import Any

from .enums import DeploymentMode

_MODE_ENV_VAR = "SOLO_MODE"
_VALID_OVERRIDES = {"lite", "core", "full"}

# Patterns that are NOT valid credentials (case-insensitive check)
_PLACEHOLDER_PATTERNS = (
    "YOUR_", "YOUR", "CHANGE_ME", "CHANGE",
    "PLACEHOLDER", "XXXXX", "REPLACE", "FIXME",
    "TODO", "EXAMPLE", "TEST_",
)

# Env var name patterns — a string that looks like an env var name, not a key
_ENV_VAR_PATTERNS = (
    "API_KEY", "_KEY", "_TOKEN", "_SECRET",
    "_PASSWORD", "_ID", "_URL", "_HOST",
    "_ENDPOINT",
)


def _is_valid_credential(value: str | None) -> bool:
    """Check if a string is a real credential, not a placeholder or empty.

    Rejects:
    - None / empty string
    - Strings containing placeholder words (YOUR, CHANGE_ME, FIXME, etc.)
    - Strings that look like env var names (API_KEY, _TOKEN, etc.)
    - Short values (< 8 characters)
    """
    if not value or not value.strip():
        return False
    val = value.strip()

    # Minimum length check
    if len(val) < 8:
        return False

    # Check placeholder patterns
    val_upper = val.upper()
    for pattern in _PLACEHOLDER_PATTERNS:
        if pattern in val_upper:
            return False

    # Check if it looks like an env var name (not an actual value)
    # A real API key value does not read like a config key name
    for pattern in _ENV_VAR_PATTERNS:
        if pattern in val_upper:
            return False

    return not (val.startswith("/") or val.startswith("secret://") or val.startswith("file://"))


def _check_provider_credential(env_var: str, provider_id: str) -> dict[str, Any]:
    """Check a single provider for valid credentials.

    Reads the env var directly. Does NOT evaluate env var name as a value.
    Does NOT read from .env.example files.
    """
    raw_value = os.environ.get(env_var, "")
    has_valid = _is_valid_credential(raw_value)
    return {
        "provider": provider_id,
        "env_var": env_var,
        "configured": has_valid,
    }


def detect_mode() -> DeploymentMode:
    """Detect highest available mode based on installed dependencies.

    This represents what the system CAN run, not what it IS running.
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

    Fields:
        requested_mode:         User override (SOLO_MODE env or "auto")
        active_mode:            Actual active mode after capability check
        lite_readiness:         Whether Lite mode is ready (always true)
        optional_capabilities:  List of extra tools detected
        model_credentials:      Provider credential status
        full_mode_readiness:    Full mode prerequisites and overall ready flag
    """
    override = os.environ.get(_MODE_ENV_VAR, "").strip().lower()
    requested = override if override in _VALID_OVERRIDES else "auto"

    # Detect capabilities
    has_httpx = importlib.util.find_spec("httpx") is not None
    has_playwright = importlib.util.find_spec("playwright") is not None
    has_node = shutil.which("node") is not None
    has_docker = _check_docker()
    has_git = shutil.which("git") is not None

    # GPU detection — check for nvidia-smi or CUDA
    has_gpu = shutil.which("nvidia-smi") is not None or _check_cuda()

    # Credential detection — only real keys, not placeholders
    provider_checks = [
        _check_provider_credential("DEEPSEEK_API_KEY", "deepseek"),
        _check_provider_credential("OPENAI_API_KEY", "openai"),
        _check_provider_credential("ZHIPU_API_KEY", "zhipu"),
    ]
    any_creds = any(p["configured"] for p in provider_checks)
    active_providers = [p["provider"] for p in provider_checks if p["configured"]]

    # Full mode readiness
    full_deps_ready = {
        "docker": has_docker,
        "node": has_node,
        "gpu": has_gpu,
        "api_keys": any_creds,
    }
    full_ready = all(full_deps_ready.values())

    # Active mode determination
    # Never auto-upgrade to full or core without explicit user request
    if requested == "lite":
        active = DeploymentMode.LITE
    elif requested == "core":
        active = DeploymentMode.CORE if (has_httpx and has_playwright) else DeploymentMode.LITE
    elif requested == "full":
        active = DeploymentMode.FULL if full_ready else DeploymentMode.LITE
    else:
        # auto: always lite by default
        active = DeploymentMode.LITE

    # Optional capabilities
    optional_capabilities = []
    if has_httpx:
        optional_capabilities.append("httpx")
    if has_playwright:
        optional_capabilities.append("playwright")
    if has_node:
        optional_capabilities.append("node")
    if has_git:
        optional_capabilities.append("git")
    if any_creds:
        optional_capabilities.append("api_keys")
    if has_docker:
        optional_capabilities.append("docker")
    if has_gpu:
        optional_capabilities.append("gpu")

    return {
        "requested_mode": requested,
        "active_mode": active.value,
        "lite_readiness": True,
        "optional_capabilities": optional_capabilities,
        "model_credentials": {
            "any_configured": any_creds,
            "providers": active_providers,
        },
        "full_mode_readiness": {
            "docker": has_docker,
            "node": has_node,
            "gpu": has_gpu,
            "api_keys": any_creds,
            "ready": full_ready,
        },
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


def _check_cuda() -> bool:
    """Check if CUDA is accessible."""
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
