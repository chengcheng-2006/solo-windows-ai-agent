from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import ntsecuritycon
import win32api
import win32crypt
import win32security


ROOT = Path(r"D:\OpenClaw-Hermes-Integration")
DEFAULT_ROOT = ROOT / "state" / "task-inputs"
TASK_ID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")


class TaskInputStore(Protocol):
    def put(self, task_id: str, objective: str, metadata: dict[str, Any] | None = None) -> str: ...
    def get(self, input_ref: str) -> str: ...
    def get_document(self, input_ref: str) -> dict[str, Any]: ...
    def delete(self, task_id: str) -> bool: ...
    def health(self) -> bool: ...


def _private_acl(path: Path) -> None:
    user_sid = win32security.LookupAccountName(None, win32api.GetUserName())[0]
    system_sid = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid, None)
    dacl = win32security.ACL()
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, ntsecuritycon.FILE_ALL_ACCESS, user_sid)
    dacl.AddAccessAllowedAce(win32security.ACL_REVISION, ntsecuritycon.FILE_ALL_ACCESS, system_sid)
    win32security.SetNamedSecurityInfo(
        str(path), win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        None, None, dacl, None,
    )


def _task_id_from_ref(input_ref: str) -> str:
    prefix = "input://task/"
    if not input_ref.startswith(prefix):
        raise ValueError("unsupported input reference")
    task_id = input_ref[len(prefix):]
    if not TASK_ID_RE.fullmatch(task_id):
        raise ValueError("invalid input reference")
    return task_id.lower()


class DpapiTaskInputVault:
    def __init__(self, root: Path = DEFAULT_ROOT) -> None:
        self.root = root.resolve(strict=False)
        if str(self.root).upper().startswith("E:\\") or not self.root.is_relative_to(ROOT):
            raise ValueError("task input vault must remain inside the D project root")
        self.root.mkdir(parents=True, exist_ok=True)
        _private_acl(self.root)

    def put(self, task_id: str, objective: str, metadata: dict[str, Any] | None = None) -> str:
        normalized = _task_id_from_ref(f"input://task/{task_id}")
        document = json.dumps({
            "schema": "paios.task.input.v1", "task_id": normalized,
            "objective": objective, "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).astimezone().isoformat(),
        }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        protected = win32crypt.CryptProtectData(document, "PAIOS task input", None, None, None, 0x1)
        envelope = json.dumps({
            "schema": "paios.dpapi.task-input.v1", "scope": "CurrentUser",
            "ciphertext": base64.b64encode(protected).decode("ascii"),
        }, ensure_ascii=True, separators=(",", ":")).encode("ascii")
        target = self.root / f"{normalized}.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(envelope)
        os.replace(temporary, target)
        _private_acl(target)
        return f"input://task/{normalized}"

    def get(self, input_ref: str) -> str:
        return str(self.get_document(input_ref)["objective"])

    def get_document(self, input_ref: str) -> dict[str, Any]:
        task_id = _task_id_from_ref(input_ref)
        envelope = json.loads((self.root / f"{task_id}.json").read_text(encoding="ascii"))
        if envelope.get("schema") != "paios.dpapi.task-input.v1":
            raise ValueError("unsupported task input envelope")
        blob = base64.b64decode(envelope["ciphertext"], validate=True)
        document = json.loads(win32crypt.CryptUnprotectData(blob, None, None, None, 0x1)[1].decode("utf-8"))
        if document.get("task_id") != task_id:
            raise ValueError("task input binding mismatch")
        metadata = document.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("task input metadata must be an object")
        return {"task_id": task_id, "objective": str(document["objective"]), "metadata": metadata}

    def delete(self, task_id: str) -> bool:
        normalized = _task_id_from_ref(f"input://task/{task_id}")
        target = self.root / f"{normalized}.json"
        if target.exists():
            target.unlink()
        return not target.exists()

    def health(self) -> bool:
        return self.root.is_dir() and os.access(self.root, os.R_OK | os.W_OK)


class InMemoryTaskInputVault:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def put(self, task_id: str, objective: str, metadata: dict[str, Any] | None = None) -> str:
        task_id = _task_id_from_ref(f"input://task/{task_id}")
        self.values[task_id] = json.dumps({"objective": objective, "metadata": metadata or {}}, ensure_ascii=False)
        return f"input://task/{task_id}"

    def get(self, input_ref: str) -> str:
        return str(self.get_document(input_ref)["objective"])

    def get_document(self, input_ref: str) -> dict[str, Any]:
        task_id = _task_id_from_ref(input_ref)
        value = json.loads(self.values[task_id])
        return {"task_id": task_id, "objective": value["objective"], "metadata": value["metadata"]}

    def delete(self, task_id: str) -> bool:
        self.values.pop(_task_id_from_ref(f"input://task/{task_id}"), None)
        return True

    def health(self) -> bool:
        return True
