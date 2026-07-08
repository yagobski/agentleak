"""Multi-style text sanitizer (redaction defense).

Supports 6 redaction styles:

* ``placeholder`` — ``[REDACTED_SSN]``  (default, most readable)
* ``asterisk``    — ``***-**-****``
* ``masked``      — ``XXX-XX-6789``  (keeps last 4 for recognition)
* ``hash``        — SHA-256 of the value, truncated to 16 hex chars
* ``category``    — ``[PII: SSN]``
* ``remove``      — delete the token entirely

The sanitizer applies the built-in regex detectors (Tier 1) over a piece of
text and replaces every hit.  It is *not* the full analysis pipeline — it
operates on raw text and is designed to be fast and dependency-free so it can
be used as a real-time guardrail inside integrations.

Usage::

    from agentleak.defenses import sanitize_text, Sanitizer

    clean = sanitize_text("SSN: 412-55-9087 — do not share!", style="placeholder")
    # "SSN: [REDACTED_SSN] — do not share!"

    s = Sanitizer(style="masked")
    clean2 = s.sanitize(tool_response_text)
"""

from __future__ import annotations

import hashlib
import re
from enum import Enum
from typing import Any


class RedactionStyle(str, Enum):
    PLACEHOLDER = "placeholder"  # [REDACTED_<TYPE>]
    ASTERISK = "asterisk"        # ****
    MASKED = "masked"            # XXX-XX-6789 (last 4 visible)
    HASH = "hash"                # sha256[:16]
    CATEGORY = "category"        # [PII: SSN]
    REMOVE = "remove"            # deleted


# ---------------------------------------------------------------------------
# Regex patterns for common sensitive data types (fast, no external deps)
# Patterns are a simplified subset of the full detector; sufficient for
# real-time sanitization.
# ---------------------------------------------------------------------------
_PATTERNS: list[tuple[str, str]] = [
    # (data_type, pattern)
    ("SSN",         r"\b\d{3}-\d{2}-\d{4}\b"),
    ("CREDIT_CARD", r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11})\b"),
    ("EMAIL",       r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"),
    ("PHONE",       r"\b\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    ("IBAN",        r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    ("API_KEY",     r"\b(?:sk-|pk-|token_|api_key_)[A-Za-z0-9_\-]{16,64}\b"),
    ("JWT",         r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"),
    ("AWS_KEY",     r"\bAKIA[0-9A-Z]{16}\b"),
    ("HEALTH_ID",   r"\b[A-Z]{4}\d{8}\b"),
    ("CANARY",      r"\bCANARY_[A-Z0-9]{8}\b"),
]

_COMPILED: list[tuple[str, re.Pattern[str]]] = [
    (dt, re.compile(pat)) for dt, pat in _PATTERNS
]


def _redact_value(value: str, dtype: str, style: RedactionStyle) -> str:
    """Apply the chosen redaction style to a single matched value."""
    if style == RedactionStyle.PLACEHOLDER:
        return f"[REDACTED_{dtype}]"
    if style == RedactionStyle.ASTERISK:
        return "*" * len(value)
    if style == RedactionStyle.MASKED:
        visible = min(4, len(value))
        return "X" * (len(value) - visible) + value[-visible:]
    if style == RedactionStyle.HASH:
        h = hashlib.sha256(value.encode()).hexdigest()
        return h[:16]
    if style == RedactionStyle.CATEGORY:
        return f"[PII: {dtype}]"
    if style == RedactionStyle.REMOVE:
        return ""
    return f"[REDACTED_{dtype}]"


class Sanitizer:
    """Apply regex-based redaction to raw text strings.

    Args:
        style: One of the :class:`RedactionStyle` values (default ``placeholder``).
        extra_patterns: Additional ``(data_type, regex_pattern)`` tuples to
            include on top of the built-in set.
    """

    def __init__(
        self,
        style: str | RedactionStyle = RedactionStyle.PLACEHOLDER,
        extra_patterns: list[tuple[str, str]] | None = None,
    ) -> None:
        self.style = RedactionStyle(style) if isinstance(style, str) else style
        self._patterns = list(_COMPILED)
        if extra_patterns:
            self._patterns.extend(
                (dt, re.compile(pat)) for dt, pat in extra_patterns
            )

    def sanitize(self, text: str) -> str:
        """Return *text* with all detected sensitive values replaced."""
        if not text:
            return text
        for dtype, pattern in self._patterns:
            def _replace(m: re.Match, _dtype: str = dtype, _style: RedactionStyle = self.style) -> str:
                return _redact_value(m.group(0), _dtype, _style)
            text = pattern.sub(_replace, text)
        return text

    def sanitize_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively sanitize all string values in a dict."""
        out: dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, str):
                out[k] = self.sanitize(v)
            elif isinstance(v, dict):
                out[k] = self.sanitize_dict(v)
            elif isinstance(v, list):
                out[k] = [
                    self.sanitize(item) if isinstance(item, str) else item
                    for item in v
                ]
            else:
                out[k] = v
        return out

    def redaction_count(self, text: str) -> int:
        """Count the total number of redactions that *would* be applied."""
        if not text:
            return 0
        count = 0
        for _, pattern in self._patterns:
            count += len(pattern.findall(text))
        return count


def sanitize_text(
    text: str,
    *,
    style: str | RedactionStyle = RedactionStyle.PLACEHOLDER,
    extra_patterns: list[tuple[str, str]] | None = None,
) -> str:
    """One-shot convenience function for sanitizing a text string."""
    return Sanitizer(style=style, extra_patterns=extra_patterns).sanitize(text)
