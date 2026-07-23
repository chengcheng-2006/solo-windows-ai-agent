from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ROOT = Path(r"D:\OpenClaw-Hermes-Integration")


@dataclass(frozen=True)
class Settings:
    root: Path = DEFAULT_ROOT
    db_path: Path = DEFAULT_ROOT / "database" / "night_workflows.db"
    manifest_path: Path = DEFAULT_ROOT / "workflow" / "manifests" / "openclaw_hermes_v1.json"
    logs_dir: Path = DEFAULT_ROOT / "logs"
    runtime_dir: Path = DEFAULT_ROOT / "runtime"
    evidence_dir: Path = DEFAULT_ROOT / "evidence"


def get_settings(root: str | os.PathLike[str] | None = None) -> Settings:
    base = Path(root or os.environ.get("OPENCLAW_NIGHT_ROOT") or DEFAULT_ROOT)
    return Settings(
        root=base,
        db_path=base / "database" / "night_workflows.db",
        manifest_path=base / "workflow" / "manifests" / "openclaw_hermes_v1.json",
        logs_dir=base / "logs",
        runtime_dir=base / "runtime",
        evidence_dir=base / "evidence",
    )


def ensure_directories(settings: Settings) -> None:
    for path in [
        settings.db_path.parent,
        settings.logs_dir,
        settings.runtime_dir,
        settings.evidence_dir,
        settings.root / "workflow" / "manifests",
        settings.root / "workflow" / "policies",
    ]:
        path.mkdir(parents=True, exist_ok=True)

