from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ntsecuritycon
import win32api
import win32crypt
import win32security
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


ROOT = Path(r"D:\OpenClaw-Hermes-Integration")
# Production defaults (matching config/privacy_master_production.json)
DEFAULT_STORE = ROOT / "state" / "privacy-broker" / "dpapi-store.json"
DEFAULT_MASTER = ROOT / "state" / "privacy-broker" / "master.json"
DEFAULT_AUDIT = ROOT / "state" / "privacy-broker" / "audit.jsonl"
SECRET_REF_RE = re.compile(r"^secret://[a-z0-9][a-z0-9._/-]{2,255}$", re.IGNORECASE)
PII_TOKEN_RE = re.compile(r"pii://[a-z_]+/[A-Za-z0-9_-]{16,}")
PII_PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "phone": re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)"),
    "identity": re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)"),
    "secret_assignment": re.compile(r"(?i)\b(?:api[_-]?key|password|passwd|token|secret)\s*[:=]\s*(?!//)\S+"),
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _private_acl(path: Path) -> None:
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


@dataclass
class Lease:
    ref: str
    target_pid: int
    target_name: str
    expires_at: float
    remaining_uses: int
    unlock_token: str | None


class PrivacyBroker:
    def __init__(self, store: Path = DEFAULT_STORE, master: Path = DEFAULT_MASTER, audit: Path = DEFAULT_AUDIT) -> None:
        self.store = Path(store).resolve(strict=False)
        self.master = Path(master).resolve(strict=False)
        self.audit = Path(audit).resolve(strict=False)
        for path in (self.store, self.master, self.audit):
            if str(path).upper().startswith("E:\\") or not path.is_relative_to(ROOT):
                raise ValueError("Privacy Broker path outside project root")
        self._unlocks: dict[str, float] = {}
        self._leases: dict[str, Lease] = {}
        self._pii_tokens: dict[str, str] = {}
        self._failed_unlocks = 0
        self._locked_until = 0.0
        self._hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)

    def _write_private(self, path: Path, document: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(document, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        _private_acl(temporary)
        os.replace(temporary, path)
        _private_acl(path)

    def _audit(self, action: str, result: str, **metadata: Any) -> None:
        self.audit.parent.mkdir(parents=True, exist_ok=True)
        event = {"schema": "paios.privacy.audit.v1", "timestamp": _now(), "action": action, "result": result, **metadata}
        encoded = json.dumps(event, ensure_ascii=True, separators=(",", ":"))
        if any(pattern.search(encoded) for pattern in PII_PATTERNS.values()):
            raise ValueError("audit event contains sensitive material")
        with self.audit.open("a", encoding="utf-8") as handle:
            handle.write(encoded + "\n")
        _private_acl(self.audit)

    def configure_master(self, master_password: str) -> None:
        if len(master_password) < 14:
            raise ValueError("master password is too short")
        self._write_private(
            self.master,
            {"schema": "paios.privacy.master.v1", "algorithm": "argon2id", "password_hash": self._hasher.hash(master_password)},
        )
        self._audit("master.configure", "PASS", algorithm="argon2id")

    def unlock(self, master_password: str, ttl_seconds: int = 120) -> str:
        now = time.monotonic()
        if now < self._locked_until:
            self._audit("master.unlock", "DENIED_LOCKOUT", retry_after_seconds=int(self._locked_until - now))
            raise PermissionError("unlock temporarily locked")
        document = json.loads(self.master.read_text(encoding="utf-8"))
        try:
            self._hasher.verify(document["password_hash"], master_password)
        except VerifyMismatchError:
            self._failed_unlocks += 1
            if self._failed_unlocks >= 5:
                self._locked_until = now + 60
            self._audit("master.unlock", "DENIED", failure_count=self._failed_unlocks)
            raise PermissionError("invalid master password") from None
        self._failed_unlocks = 0
        token = secrets.token_urlsafe(32)
        self._unlocks[token] = now + min(max(ttl_seconds, 10), 300)
        self._audit("master.unlock", "PASS", ttl_seconds=min(max(ttl_seconds, 10), 300))
        return token

    def lock(self, unlock_token: str) -> None:
        self._unlocks.pop(unlock_token, None)
        self._audit("master.lock", "PASS")

    def _is_unlocked(self, token: str | None) -> bool:
        if not token:
            return False
        expires = self._unlocks.get(token, 0)
        if expires < time.monotonic():
            self._unlocks.pop(token, None)
            return False
        return True

    def register_secret(self, ref: str, value: str, purpose: str, *, high_sensitivity: bool = False) -> None:
        if not SECRET_REF_RE.fullmatch(ref) or not value or len(value) > 65536:
            raise ValueError("invalid secret registration")
        document = {"schema": "paios.privacy.dpapi.v1", "scope": "CurrentUser", "entries": {}}
        if self.store.exists():
            document = json.loads(self.store.read_text(encoding="utf-8"))
        protected = win32crypt.CryptProtectData(value.encode("utf-8"), "PAIOS Privacy Broker", None, None, None, 0x1)
        document["entries"][ref] = {
            "ciphertext": base64.b64encode(protected).decode("ascii"),
            "purpose": purpose[:200],
            "high_sensitivity": high_sensitivity,
            "updated_at": _now(),
        }
        self._write_private(self.store, document)
        self._audit("secret.register", "PASS", ref=ref, high_sensitivity=high_sensitivity)

    def create_lease(
        self, ref: str, target_pid: int, target_name: str, *, ttl_seconds: int = 30,
        max_uses: int = 1, unlock_token: str | None = None,
    ) -> str:
        document = json.loads(self.store.read_text(encoding="utf-8"))
        entry = document.get("entries", {}).get(ref)
        if not entry:
            raise KeyError("SecretRef not found")
        if entry.get("high_sensitivity") and not self._is_unlocked(unlock_token):
            self._audit("lease.create", "DENIED_UNLOCK_REQUIRED", ref=ref, target_name=target_name)
            raise PermissionError("active unlock session required")
        if target_pid <= 0 or not target_name or not 1 <= max_uses <= 3:
            raise ValueError("invalid lease policy")
        lease_id = secrets.token_urlsafe(32)
        self._leases[lease_id] = Lease(
            ref=ref, target_pid=target_pid, target_name=target_name[:128],
            expires_at=time.monotonic() + min(max(ttl_seconds, 1), 120), remaining_uses=max_uses,
            unlock_token=unlock_token,
        )
        self._audit("lease.create", "PASS", ref=ref, target_pid=target_pid, target_name=target_name[:128], ttl_seconds=min(max(ttl_seconds, 1), 120), max_uses=max_uses)
        return lease_id

    def consume_lease(self, lease_id: str, target_pid: int) -> str:
        lease = self._leases.get(lease_id)
        result = "DENIED"
        try:
            if not lease or lease.expires_at < time.monotonic() or lease.remaining_uses <= 0:
                raise PermissionError("lease expired or consumed")
            if target_pid != lease.target_pid:
                raise PermissionError("lease target mismatch")
            document = json.loads(self.store.read_text(encoding="utf-8"))
            encoded = document["entries"][lease.ref]["ciphertext"]
            plaintext = win32crypt.CryptUnprotectData(base64.b64decode(encoded, validate=True), None, None, None, 0x1)[1]
            lease.remaining_uses -= 1
            if lease.remaining_uses <= 0:
                self._leases.pop(lease_id, None)
            result = "PASS"
            return plaintext.decode("utf-8")
        finally:
            self._audit("lease.consume", result, ref=lease.ref if lease else "unknown", target_pid=target_pid)

    def tokenize_pii(self, text: str) -> dict[str, Any]:
        output = text
        tokens: list[dict[str, str]] = []
        for kind, pattern in PII_PATTERNS.items():
            def replace(match: re.Match[str]) -> str:
                token = f"pii://{kind}/{secrets.token_urlsafe(18)}"
                self._pii_tokens[token] = match.group(0)
                tokens.append({"type": kind, "token": token})
                return token
            output = pattern.sub(replace, output)
        self._audit("pii.tokenize", "PASS", token_count=len(tokens), types=sorted({item["type"] for item in tokens}))
        return {"text": output, "tokens": tokens}

    def detokenize_pii(self, text: str, *, local_target: bool) -> str:
        if not local_target:
            raise PermissionError("PII detokenization is local-only")
        output = text
        for token in PII_TOKEN_RE.findall(text):
            output = output.replace(token, self._pii_tokens.get(token, token))
        return output

    def assert_cloud_safe(self, value: str) -> None:
        value = re.sub(r"secret://[a-z0-9][a-z0-9._/-]{2,255}", "SECRET_REF", value, flags=re.IGNORECASE)
        value = PII_TOKEN_RE.sub("PII_TOKEN", value)
        for pattern in PII_PATTERNS.values():
            if pattern.search(value):
                raise ValueError("raw sensitive material blocked from cloud context")

    def remove_secret(self, ref: str) -> None:
        document = json.loads(self.store.read_text(encoding="utf-8"))
        document.get("entries", {}).pop(ref, None)
        self._write_private(self.store, document)
        self._audit("secret.remove", "PASS", ref=ref)

    def clear_memory(self) -> None:
        self._unlocks.clear()
        self._leases.clear()
        self._pii_tokens.clear()
        self._audit("memory.clear", "PASS")
