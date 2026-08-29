# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Multi-style text sanitizer (redaction defense).

Supports 6 redaction styles:

* ``placeholder`` — ``[REDACTED_SSN]``  (default, most readable)
* ``asterisk``    — ``***-**-****``
* ``masked``      — ``XXX-XX-6789``  (keeps last 4 for recognition)
* ``hash``        — SHA-256 of the value, truncated to 16 hex chars
* ``category``    — ``[PII: SSN]``
* ``remove``      — delete the token entirely

The sanitizer applies the built-in regex detectors (Tier 1) over a piece of
text and replaces every hit.  It is *not* the full analysis pipeline — no
Presidio, no semantic judge — but it reads from the *same* detector registry
the analysis does, so anything AgentLeak can find, AgentLeak can remove.

That parity is the point, and it is new. This module used to carry its own
hand-written table of ten patterns, described in a comment as "a simplified
subset of the full detector". The subset had drifted: it had no pattern for a
Canadian SIN in any format, none for a diagnosis or a medication, its credit
card required contiguous digits so `4111 1111 1111 1111` passed straight
through, and its health identifier could not match the `TR12345678` in this
project's own demo trace. The detectors found all of them. The redactor —
exposed to coding agents as an MCP tool, and used as a runtime guardrail —
returned text that looked sanitised and was not. A privacy tool that quietly
hands back unsanitised text is the one failure that does not survive being
found by somebody else.

Any data type the detectors emit but the sanitizer must not remove has to say
so out loud in :data:`DETECT_ONLY`; :func:`redaction_coverage` reports the
split, and a conformance test fails on a type that is in neither camp.

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
# Structural patterns the value detectors do not own.
#
# Everything with a *data type* now comes from the detector registry below, so
# the two inventories cannot drift again. What stays here is the handful of
# markers that belong to the defense rather than to detection.
# ---------------------------------------------------------------------------
_EXTRA_PATTERNS: list[tuple[str, str]] = [
    # Canary tokens are planted by the auditor, not found in the wild, so no
    # detector owns them — but a guardrail must still strip them.
    ("CANARY", r"\bCANARY_[A-Z0-9]{8}\b"),
]

_COMPILED_EXTRA: list[tuple[str, re.Pattern[str]]] = [
    (dt, re.compile(pat)) for dt, pat in _EXTRA_PATTERNS
]

# Data types AgentLeak can *find* but deliberately does not *remove*.
#
# A type belongs here only when redaction would destroy the meaning of the text
# without protecting a person, and each entry carries the reason. Everything
# else the detectors emit must be redactable; ``tests/test_redaction_parity.py``
# fails on a type that is in neither camp.
DETECT_ONLY: dict[str, str] = {
    "employment_status": (
        "A status word ('terminated', 'on leave') carries no identifier on its "
        "own; removing it deletes the sentence's meaning and re-identifies "
        "nobody. It is scored, not stripped."
    ),
    "internal_note": (
        "Marks a passage as internal rather than naming a value to remove; "
        "the sensitive content inside it is caught by its own detectors."
    ),
    "secret_assignment": (
        "Flags the shape 'KEY = <value>' in source code. The credential itself "
        "is redacted by the credential detectors; blanking the assignment would "
        "remove the code."
    ),
}


def _default_detectors() -> list[Any]:
    """The Tier-1 detector chain, built once and shared.

    A guardrail runs on the hot path, so the chain is cached at module level;
    detectors are stateless over ``detect()``.
    """
    global _DETECTOR_CACHE
    if _DETECTOR_CACHE is None:
        from ..detectors import build_detectors

        _DETECTOR_CACHE = build_detectors(None, None)
    return _DETECTOR_CACHE


_DETECTOR_CACHE: list[Any] | None = None


def redaction_coverage() -> dict[str, Any]:
    """What this sanitizer can remove, straight from the running software.

    Reported through ``GET /api/meta`` so the claim "anything we detect, we can
    redact" is verifiable in one request rather than asserted in a README.
    """
    import inspect
    import re as _re

    emitted: set[str] = set()
    for detector in _default_detectors():
        source = inspect.getsource(type(detector))
        emitted |= set(_re.findall(r'data_type\s*=\s*"([a-z_]+)"', source))
        emitted |= set(_re.findall(r'"([a-z_]+)",\s*Severity\.', source))

    redactable = sorted(emitted - set(DETECT_ONLY))
    return {
        "redactable": redactable,
        "redactable_count": len(redactable),
        "detect_only": {k: v for k, v in sorted(DETECT_ONLY.items()) if k in emitted},
        "extra": sorted(dt for dt, _ in _EXTRA_PATTERNS),
    }


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
        detectors: list[Any] | None = None,
    ) -> None:
        self.style = RedactionStyle(style) if isinstance(style, str) else style
        self._detectors = _default_detectors() if detectors is None else detectors
        self._patterns = list(_COMPILED_EXTRA)
        if extra_patterns:
            self._patterns.extend(
                (dt, re.compile(pat)) for dt, pat in extra_patterns
            )

    # ------------------------------------------------------------------
    def _spans(self, text: str) -> list[tuple[int, int, str, str]]:
        """Every region to redact, as non-overlapping ``(start, end, value, type)``.

        Spans are resolved before any substitution rather than applying one
        pattern after another over a mutating string. Sequential substitution
        lets a later pattern match inside an earlier replacement — and it lets a
        short match blank part of a longer one, leaving the tail of a credential
        in the "sanitised" output.

        Where spans nest, the *inner* ones win. A key-name match locates a
        secret only as precisely as the surrounding punctuation allows, so
        ``ssn: 412-55-9087 and more text`` yields one span over the whole tail;
        the SSN pattern inside it says exactly where the secret is. Keeping the
        outer span would delete the sentence. An outer span with nothing inside
        it is kept, because then it is the only signal there is — which is the
        whole reason the key-name detector exists, for the rare diagnosis or the
        experimental drug no dictionary lists.

        The trade-off is real and it is chosen, not accidental. Preferring the
        inner span can leave a modifier behind — ``diagnosis: Type 2 diabetes``
        redacts to ``diagnosis: Type 2 [REDACTED_HEALTH_CONDITION]``, because
        the dictionary match is ``diabetes``. A modifier is not a
        re-identifier, and the alternative rule deletes the rest of any
        sentence a sensitive key appears in, which is how a guardrail gets
        switched off. Run ``--mode standard`` when spans must be exact.
        """
        found: list[tuple[int, int, str, str]] = []

        for detector in self._detectors:
            for raw in detector.detect(text):
                if raw.data_type in DETECT_ONLY:
                    continue
                value = str(raw.matched_value)
                if not value:
                    continue
                start = text.find(value)
                while start >= 0:
                    found.append((start, start + len(value), value, raw.data_type.upper()))
                    start = text.find(value, start + 1)

        for dtype, pattern in self._patterns:
            for match in pattern.finditer(text):
                found.append((match.start(), match.end(), match.group(0), dtype))

        # Drop any span that strictly contains another: the inner span is a
        # more precise reading of the same signal.
        inner = [
            span for span in found
            if not any(
                other is not span
                and other[0] >= span[0]
                and other[1] <= span[1]
                and (other[1] - other[0]) < (span[1] - span[0])
                for other in found
            )
        ]

        # Whatever still overlaps only does so partially — two detectors
        # bracketing one credential differently. Take it whole rather than
        # trimming to the shorter, which would leave a tail behind.
        inner.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        resolved: list[tuple[int, int, str, str]] = []
        cursor = -1
        for span in inner:
            if span[0] >= cursor:
                resolved.append(span)
                cursor = span[1]
        return resolved

    def sanitize(self, text: str) -> str:
        """Return *text* with all detected sensitive values replaced."""
        if not text:
            return text
        out: list[str] = []
        cursor = 0
        for start, end, value, dtype in self._spans(text):
            out.append(text[cursor:start])
            out.append(_redact_value(value, dtype, self.style))
            cursor = end
        out.append(text[cursor:])
        return "".join(out)

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
        return len(self._spans(text))


def sanitize_text(
    text: str,
    *,
    style: str | RedactionStyle = RedactionStyle.PLACEHOLDER,
    extra_patterns: list[tuple[str, str]] | None = None,
    detectors: list[Any] | None = None,
) -> str:
    """One-shot convenience function for sanitizing a text string."""
    return Sanitizer(
        style=style, extra_patterns=extra_patterns, detectors=detectors
    ).sanitize(text)
