"""Fail-closed redaction for runner logs and persisted error summaries."""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

_SECRET_KEY = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|authorization|cookie|"
    r"private[\\s_-]?key|connection[\\s_-]?string|credential)",
    re.IGNORECASE,
)
_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|"
               r"password|client[_-]?secret)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)\b(postgres(?:ql)?://)[^\s'\"<>]+"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\."
               r"[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?"
               r"-----END [A-Z ]*PRIVATE KEY-----"),
)
_REDACTED = "[REDACTED]"
_MAX_TEXT = 1200
_MAX_DEPTH = 8
_MAX_ITEMS = 100


def redact_text(value: str) -> str:
    """Redact common credential formats; truncate after redaction."""
    result = value
    for pattern in _PATTERNS:
        result = pattern.sub(_REDACTED, result)
    return result[:_MAX_TEXT]


def safe_metadata(value: Any, *, _depth: int = 0) -> Any:
    """Return bounded JSON-safe metadata with secret-bearing keys removed."""
    if _depth > _MAX_DEPTH:
        return "[TRUNCATED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _MAX_ITEMS:
                result["_truncated"] = True
                break
            safe_key = redact_text(str(key))[:100]
            if _SECRET_KEY.search(str(key)):
                result[safe_key] = _REDACTED
            else:
                result[safe_key] = safe_metadata(item, _depth=_depth + 1)
        return result
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [safe_metadata(item, _depth=_depth + 1)
                for item in list(value)[:_MAX_ITEMS]]
    return "[UNSUPPORTED]"


def safe_json(value: Any) -> str:
    """Serialize allowlisted metadata; never serialize arbitrary objects."""
    return json.dumps(safe_metadata(value), ensure_ascii=False, separators=(",", ":"))
