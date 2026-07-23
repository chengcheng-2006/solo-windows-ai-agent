from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

# Suppress console window for subprocess calls on Windows; no-op on other platforms
_CW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

from workers.vision_worker import OCRWorker, ScreenshotWorker

from .registry import CAPABILITIES
from .security import canonical_request, verify_token
from .uia import UIAWorker


ROOT = Path(r"D:\OpenClaw-Hermes-Integration")
WRITE_ROOTS = tuple((ROOT / name).resolve() for name in ("artifacts", "workspaces")) + ((ROOT / "tests" / "runtime-sandbox").resolve(),)


def _path(value: str, *, write: bool = False) -> Path:
    path = Path(value).resolve(strict=not write)
    if str(path).upper().startswith("E:\\") or not path.is_relative_to(ROOT):
        raise ValueError("path is outside project root")
    if write and not any(path.is_relative_to(root) for root in WRITE_ROOTS):
        raise ValueError("write path is outside approved roots")
    return path


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _approval_valid(request: dict) -> bool:
    approval = request.get("approval") or {}
    canonical = canonical_request(request["task_id"], request["capability"], request["params"], request["expires_at"])
    return approval.get("canonical_sha256") == hashlib.sha256(canonical).hexdigest() and int(approval.get("expires_at", 0)) >= request["expires_at"]


def dispatch(request: dict) -> dict:
    if not verify_token(request):
        raise PermissionError("invalid or expired task token")
    capability = request["capability"]
    spec = CAPABILITIES.get(capability)
    if not spec:
        raise ValueError("unknown capability")
    if spec.approval_required and not _approval_valid(request):
        raise PermissionError("bound approval is required")
    params = request["params"]
    if capability in {"filesystem.read", "document.read"}:
        path = _path(params["path"])
        return {"content": path.read_text(encoding="utf-8"), "sha256": _hash(path)}
    if capability in {"filesystem.write", "document.write"}:
        path = _path(params["path"], write=True)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(params["content"], encoding="utf-8")
        return {"sha256": _hash(path)}
    if capability == "filesystem.copy":
        source, destination = _path(params["source"]), _path(params["destination"], write=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if _hash(source) != _hash(destination):
            raise RuntimeError("copy hash mismatch")
        return {"sha256": _hash(destination)}
    if capability == "filesystem.move":
        source, destination = _path(params["source"]), _path(params["destination"], write=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        expected = _hash(source)
        shutil.move(source, destination)
        return {"sha256": _hash(destination), "verified": _hash(destination) == expected and not source.exists()}
    if capability == "filesystem.delete":
        path = _path(params["path"], write=True)
        expected = _hash(path)
        path.unlink()
        return {"deleted": not path.exists(), "sha256": expected}
    if capability == "archive.extract":
        source, destination = _path(params["archive"]), _path(params["destination"], write=True)
        destination.mkdir(parents=True, exist_ok=True)
        outputs = []
        with zipfile.ZipFile(source) as archive:
            for member in archive.infolist():
                target = (destination / member.filename).resolve()
                if not target.is_relative_to(destination):
                    raise ValueError("archive path traversal rejected")
            archive.extractall(destination)
            outputs = [str((destination / member.filename).resolve()) for member in archive.infolist()]
        return {"files": outputs}
    if capability == "powershell.execute":
        cwd = _path(params.get("cwd", str(ROOT)))
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "-"],
            input=params["script"], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=min(spec.timeout_seconds, int(params.get("timeout_seconds", spec.timeout_seconds))),
            creationflags=_CW,
        )
        return {"exit_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
    if capability == "ocr.read":
        return OCRWorker().read(_path(params["path"]))
    if capability == "screenshot.capture":
        return ScreenshotWorker().capture(_path(params["path"], write=True), int(params.get("monitor", 1)))
    if capability == "windows.uia.inspect":
        return UIAWorker.inspect(int(params["pid"]))
    if capability == "gpu.inference":
        payload = json.dumps({"model": params["model"], "prompt": params["prompt"], "stream": False}).encode()
        req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=spec.timeout_seconds) as response:
            return {"response": json.load(response).get("response", "")}
    if capability == "health":
        return {"status": "PASS"}
    raise NotImplementedError(f"capability adapter is not implemented: {capability}")
