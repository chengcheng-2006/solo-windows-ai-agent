from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUESTED_GEMINI_MODEL = "gemini-3-flash-preview"
DEFAULT_TIMEOUT_SECONDS = 30
API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiCredentialUnavailable(RuntimeError):
    pass


class GeminiPrivacyBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class GeminiResolution:
    requested_model: str
    resolved_model: str | None
    resolution_reason: str
    free_tier_verified: bool
    multimodal_verified: bool
    preview_or_stable: str


SENSITIVE_PATTERNS = (
    re.compile(r"(?i)\b(api[_-]?key|secret|password|passwd|cookie|session[_-]?token|authorization)\b"),
    re.compile(r"(?i)\b(bearer\s+[a-z0-9._-]{12,})\b"),
    re.compile(r"\b\d{6}\b"),
    re.compile(r"\b\d{15,19}\b"),
)


def gemini_key_present() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def classify_text_for_gemini(text: str) -> dict[str, Any]:
    hits = [idx for idx, pattern in enumerate(SENSITIVE_PATTERNS) if pattern.search(text or "")]
    blocked_reason = None
    if hits:
        blocked_reason = "SECRET_DISCLOSURE_DENIED"
    return {
        "send_allowed": not hits,
        "classification": "PUBLIC_OR_LOW_RISK" if not hits else "SENSITIVE_BLOCKED",
        "blocked_reason": blocked_reason,
        "pattern_hit_count": len(hits),
    }


def assert_text_allowed_for_gemini(text: str) -> None:
    result = classify_text_for_gemini(text)
    if not result["send_allowed"]:
        raise GeminiPrivacyBlocked(result["blocked_reason"])


def list_models(timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> list[dict[str, Any]]:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise GeminiCredentialUnavailable("GEMINI_API_KEY_PRESENT=false")
    req = urllib.request.Request(
        f"{API_BASE}/models",
        headers={"x-goog-api-key": key, "Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return list(payload.get("models", []))


def resolve_model(timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> GeminiResolution:
    models = list_models(timeout_seconds=timeout_seconds)
    names = {str(model.get("name", "")).removeprefix("models/"): model for model in models}
    if REQUESTED_GEMINI_MODEL in names:
        return GeminiResolution(
            requested_model=REQUESTED_GEMINI_MODEL,
            resolved_model=REQUESTED_GEMINI_MODEL,
            resolution_reason="requested_model_available",
            free_tier_verified=False,
            multimodal_verified=_looks_multimodal(names[REQUESTED_GEMINI_MODEL]),
            preview_or_stable="preview" if "preview" in REQUESTED_GEMINI_MODEL else "stable",
        )
    fallback = _choose_flash_multimodal(names)
    return GeminiResolution(
        requested_model=REQUESTED_GEMINI_MODEL,
        resolved_model=fallback,
        resolution_reason="requested_model_unavailable_flash_fallback" if fallback else "no_flash_multimodal_model_available",
        free_tier_verified=False,
        multimodal_verified=bool(fallback and _looks_multimodal(names[fallback])),
        preview_or_stable=("preview" if fallback and "preview" in fallback else "stable") if fallback else "unknown",
    )


def generate_text(prompt: str, *, model: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    assert_text_allowed_for_gemini(prompt)
    return _generate_content([{"text": prompt}], model=model, timeout_seconds=timeout_seconds)


def generate_from_image(prompt: str, image_path: Path, *, model: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    assert_text_allowed_for_gemini(prompt)
    resolved = image_path.resolve()
    if str(resolved).upper().startswith("E:\\"):
        raise GeminiPrivacyBlocked("E_DRIVE_PATH_BLOCKED")
    data = resolved.read_bytes()
    if len(data) > 4_000_000:
        raise GeminiPrivacyBlocked("IMAGE_TOO_LARGE_FOR_MINIMAL_TEST")
    mime = "image/png" if resolved.suffix.lower() == ".png" else "image/jpeg"
    parts = [
        {"text": prompt},
        {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode("ascii")}},
    ]
    return _generate_content(parts, model=model, timeout_seconds=timeout_seconds)


def _generate_content(parts: list[dict[str, Any]], *, model: str, timeout_seconds: int) -> dict[str, Any]:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise GeminiCredentialUnavailable("GEMINI_API_KEY_PRESENT=false")
    body = json.dumps({"contents": [{"role": "user", "parts": parts}]}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}/models/{model}:generateContent",
        data=body,
        headers={
            "x-goog-api-key": key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return {"ok": True, "status": int(resp.status), "payload": payload}
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")[:1000]
        if exc.code == 429:
            code = "FREE_TIER_RATE_LIMITED"
        elif exc.code == 403:
            code = "GEMINI_PROJECT_ACCESS_DENIED_USER_ACTION_REQUIRED"
        else:
            code = f"HTTP_{exc.code}"
        return {"ok": False, "status": int(exc.code), "code": code, "error": error_body}


def _choose_flash_multimodal(names: dict[str, dict[str, Any]]) -> str | None:
    preferred = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    for name in preferred:
        if name in names and _looks_multimodal(names[name]):
            return name
    for name, meta in sorted(names.items()):
        if "flash" in name and _looks_multimodal(meta):
            return name
    return None


def _looks_multimodal(model: dict[str, Any]) -> bool:
    methods = " ".join(str(x) for x in model.get("supportedGenerationMethods", []))
    return "generateContent" in methods
