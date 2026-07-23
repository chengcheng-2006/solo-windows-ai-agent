from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

import win32crypt
import ntsecuritycon
import win32api
import win32security


ROOT = Path(r"D:\OpenClaw-Hermes-Integration")
STORE = ROOT / "secrets" / "windows-bridge-dpapi-store.json"


def _set_private_acl(path: Path) -> None:
    user_sid = win32security.LookupAccountName(None, win32api.GetUserName())[0]
    system_sid = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid, None)
    dacl = win32security.ACL()
    inherit = win32security.OBJECT_INHERIT_ACE | win32security.CONTAINER_INHERIT_ACE
    dacl.AddAccessAllowedAceEx(win32security.ACL_REVISION_DS, inherit, ntsecuritycon.FILE_ALL_ACCESS, user_sid)
    dacl.AddAccessAllowedAceEx(win32security.ACL_REVISION_DS, inherit, ntsecuritycon.FILE_ALL_ACCESS, system_sid)
    win32security.SetNamedSecurityInfo(
        str(path), win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        None, None, dacl, None,
    )


def initialize() -> dict:
    if STORE.exists():
        return {"status": "EXISTS", "store": str(STORE)}
    STORE.parent.mkdir(parents=True, exist_ok=True)
    protected = win32crypt.CryptProtectData(secrets.token_bytes(32), "PAIOS Windows bridge auth", None, None, None, 0x1)
    document = {"schema": "paios.dpapi.windows-bridge.v1", "scope": "CurrentUser", "auth_key": base64.b64encode(protected).decode("ascii")}
    STORE.write_text(json.dumps(document, ensure_ascii=True, indent=2), encoding="utf-8")
    _set_private_acl(STORE)
    return {"status": "CREATED", "store": str(STORE)}


def load_key() -> bytes:
    document = json.loads(STORE.read_text(encoding="utf-8"))
    if document.get("schema") != "paios.dpapi.windows-bridge.v1":
        raise ValueError("unsupported bridge secret store")
    blob = base64.b64decode(document["auth_key"], validate=True)
    return win32crypt.CryptUnprotectData(blob, None, None, None, 0x1)[1]


def canonical_request(task_id: str, capability: str, params: dict, expires_at: int) -> bytes:
    document = {"task_id": task_id, "capability": capability, "params": params, "expires_at": expires_at}
    return json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def issue_token(task_id: str, capability: str, params: dict, ttl_seconds: int = 120) -> dict:
    expires_at = int(time.time()) + min(max(ttl_seconds, 1), 300)
    canonical = canonical_request(task_id, capability, params, expires_at)
    token = hmac.new(load_key(), canonical, hashlib.sha256).hexdigest()
    return {"expires_at": expires_at, "token": token, "canonical_sha256": hashlib.sha256(canonical).hexdigest()}


def verify_token(request: dict) -> bool:
    expires_at = int(request.get("expires_at", 0))
    if expires_at < int(time.time()) or expires_at > int(time.time()) + 300:
        return False
    canonical = canonical_request(request["task_id"], request["capability"], request["params"], expires_at)
    expected = hmac.new(load_key(), canonical, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, str(request.get("token", "")))
