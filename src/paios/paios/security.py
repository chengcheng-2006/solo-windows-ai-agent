from __future__ import annotations

import hashlib
import hmac
import json
import re
from pathlib import Path
from typing import Any


SECRET_REF_RE = re.compile(r"^secret://[a-z0-9][a-z0-9._/-]{2,255}$", re.IGNORECASE)
BEARER_RE = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{12,}")
API_TOKEN_RE = re.compile(r"(?i)\b(?:sk|key|token|secret)[-_][a-z0-9_-]{12,}")
JWT_RE = re.compile(r"\beyJ[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\.[a-zA-Z0-9_-]{8,}\b")
ASSIGNMENT_RE = re.compile(r"(?i)\b(?:api[_-]?key|password|passwd|token|secret)\s*[:=]\s*\S+")
SENSITIVE_KEYS = {
    "password",
    "passwd",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "authorization",
    "secret",
    "secret_value",
    "credential",
    "private_key",
}


class SecretMaterialRejected(ValueError):
    """Raised without including rejected material in the exception text."""


def is_secret_ref(value: str) -> bool:
    return bool(SECRET_REF_RE.fullmatch(value))


def looks_like_secret(value: str) -> bool:
    if is_secret_ref(value):
        return False
    return bool(
        BEARER_RE.search(value)
        or API_TOKEN_RE.search(value)
        or JWT_RE.search(value)
        or ASSIGNMENT_RE.search(value)
    )


def assert_secret_safe(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in SENSITIVE_KEYS:
                if not (isinstance(item, str) and is_secret_ref(item)):
                    raise SecretMaterialRejected(f"raw secret material rejected at {path}.{key}")
            assert_secret_safe(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_secret_safe(item, f"{path}[{index}]")
    elif isinstance(value, str) and looks_like_secret(value):
        raise SecretMaterialRejected(f"raw secret material rejected at {path}")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in SENSITIVE_KEYS and not (isinstance(item, str) and is_secret_ref(item)):
                result[str(key)] = "[REDACTED]"
            else:
                result[str(key)] = redact(item)
        return result
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str) and looks_like_secret(value):
        return "[REDACTED]"
    return value


def canonical_json(value: Any) -> str:
    assert_secret_safe(value)
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def token_matches(candidate: str | None, expected: str | None) -> bool:
    if not candidate or not expected:
        return False
    return hmac.compare_digest(
        hashlib.sha256(candidate.encode("utf-8")).digest(),
        hashlib.sha256(expected.encode("utf-8")).digest(),
    )

