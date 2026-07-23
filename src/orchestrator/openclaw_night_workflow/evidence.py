from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .schemas import utc_now


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_file_manifest(root: Path, out_path: Path) -> None:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and ".venv" not in path.parts:
            files.append({
                "path": str(path.relative_to(root)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"created_at": utc_now(), "files": files}, ensure_ascii=False, indent=2), encoding="utf-8")

