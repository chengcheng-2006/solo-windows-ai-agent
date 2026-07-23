from __future__ import annotations

import re


SECRET_PATTERNS = [
    re.compile(r"(?i)(authorization:\s*bearer\s+)[a-z0-9._\-]+"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[a-z0-9._\-]{16,}"),
    re.compile(r"(?i)(access_token\"?\s*[:=]\s*\"?)[^\"\s,]+"),
    re.compile(r"(?i)(refresh_token\"?\s*[:=]\s*\"?)[^\"\s,]+"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
]


def redact(text: str | None) -> str:
    if text is None:
        return ""
    value = str(text)
    for pattern in SECRET_PATTERNS:
        value = pattern.sub(lambda m: (m.group(1) if m.lastindex else "") + "REDACTED", value)
    return value


def contains_secret(text: str | None) -> bool:
    if text is None:
        return False
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)

