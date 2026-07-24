"""Evidence module — file integrity and manifest export."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str:
    """Compute SHA-256 hash of a file's contents.

    Returns 64-character hex string.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def export_file_manifest(workspace: str | Path, output_path: str | Path) -> dict[str, Any]:
    """Export a manifest of all files in workspace with their SHA-256 hashes.

    Returns the manifest dict and writes JSON to output_path.
    """
    workspace = Path(workspace)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    files: dict[str, str] = {}
    for f in sorted(workspace.rglob("*")):
        if f.is_file():
            rel = str(f.relative_to(workspace))
            files[rel] = sha256_file(f)

    manifest = {
        "workspace": str(workspace),
        "file_count": len(files),
        "files": files,
    }

    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
