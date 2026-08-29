# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Key-name-aware sensitivity detector.

Dictionary and pattern detectors only fire when they *recognise the value*
(``diabetes``, a NAM shape, an email). Realistic records leak plenty of
sensitive values the dictionaries have never seen — a rare diagnosis, an
experimental drug, a foreign account number. But the surrounding **field name**
is itself a strong signal: if a value sits under ``diagnosis``, ``ssn``, or
``account_number``, it is sensitive regardless of what the value looks like.

This detector reads that signal. It scans the searchable text (which renders
structured content as ``key: value | key: value`` and preserves raw JSON
``"key": "value"`` forms) and flags the value carried by a known-sensitive key.
It closes the output-only blind spot on the *internal* channels the rest of the
tool is built around.
"""

from __future__ import annotations

import re

from ..core.detector import Detector, RawMatch, Severity

# Sensitive field name (as a regex stem) -> (data_type, severity, advice).
# data_types map onto the AgentRisk taxonomy so levels resolve correctly.
_SENSITIVE_KEYS: dict[str, tuple[str, Severity, str]] = {
    r"ssn|social[_ ]?security(?:[_ ]?number)?": (
        "ssn", Severity.CRITICAL,
        "A government identifier is a direct re-identifier — never place it on internal channels.",
    ),
    r"sin|social[_ ]?insurance(?:[_ ]?number)?": (
        "sin", Severity.CRITICAL,
        "A government identifier is a direct re-identifier — never place it on internal channels.",
    ),
    r"health[_ ]?id|health[_ ]?identifier|mrn|medical[_ ]?record(?:[_ ]?number)?|nam": (
        "health_identifier", Severity.CRITICAL,
        "Health identifiers are regulated re-identifiers; mask them before any internal channel.",
    ),
    r"diagnos(?:is|es)|condition": (
        "health_condition", Severity.CRITICAL,
        "A diagnosis is special-category data; don't restate it on channels that don't need it.",
    ),
    r"medications?|prescriptions?|\bdrug\b|\brx\b": (
        "medication", Severity.CRITICAL,
        "Medication reveals conditions; share only with authorised agents.",
    ),
    r"account[_ ]?(?:number|no|id)|iban": (
        "account_number", Severity.CRITICAL,
        "Account numbers enable fraud; tokenise before internal channels.",
    ),
    r"credit[_ ]?card|card[_ ]?number|\bpan\b": (
        "credit_card", Severity.CRITICAL,
        "Card numbers are PCI-DSS regulated; never persist or forward them in the clear.",
    ),
    r"salary|compensation|base[_ ]?pay": (
        "salary", Severity.HIGH,
        "Compensation is sensitive HR data; keep it in the restricted HR file.",
    ),
    r"income": (
        "income", Severity.HIGH,
        "Income figures are sensitive financial data; minimise their spread.",
    ),
    r"credit[_ ]?score": (
        "credit_score", Severity.HIGH,
        "Credit scores are sensitive financial data; keep them out of internal channels.",
    ),
    r"date[_ ]?of[_ ]?birth|\bdob\b|birth[_ ]?date": (
        "date_of_birth", Severity.HIGH,
        "Date of birth is a re-identifying quasi-identifier; remove it from internal channels.",
    ),
    r"(?:home[_ ]?|mailing[_ ]?)?address": (
        "address", Severity.HIGH,
        "Home addresses are re-identifying; remove them from internal channels.",
    ),
    r"disciplinary(?:[_ ]?note|[_ ]?action)?": (
        "disciplinary_action", Severity.HIGH,
        "Disciplinary records are sensitive HR data; keep them restricted.",
    ),
    r"phone(?:[_ ]?number)?|telephone|mobile": (
        "phone_number", Severity.MEDIUM,
        "Phone numbers are contact PII; share only when necessary.",
    ),
    r"performance[_ ]?review": (
        "performance_review", Severity.MEDIUM,
        "Performance reviews are sensitive HR data; keep them restricted.",
    ),
    r"patient[_ ]?name|student[_ ]?name|customer[_ ]?name|full[_ ]?name": (
        "person_name", Severity.LOW,
        "Names are PII; avoid restating them on channels that don't need them.",
    ),
}

# Values that are not real leaks — empty, placeholders, or already redacted.
_TRIVIAL_VALUE_RE = re.compile(
    r"^(?:none|null|n/?a|true|false|redacted|unknown|\?+|-+|x{3,}|\*{2,}|"
    r"<[^>]*>|\{\{.*|\$\{.*)$",
    re.IGNORECASE,
)


# The longest value we will believe a sensitive key carries. Past this, the
# capture has stopped describing a field and started swallowing narrative, so
# the match is dropped rather than stored: an unbounded span is not evidence,
# and it would enter scoring as its own "distinct secret".
_MAX_VALUE_LEN = 120

# Trailing characters that belong to the sentence, not to the value.
_VALUE_TAIL_RE = re.compile(r"[\s.;:!?)\]]+$")


def _compile(stem: str) -> re.Pattern[str]:
    """Compile the key-name pattern for one sensitive-field stem.

    The value runs up to the next *field* delimiter — quote, pipe, comma,
    semicolon, closing brace, newline — or up to the end of the *sentence*.

    That last clause is what keeps prose honest. ``final_output``, ``log`` and
    ``inter_agent_message`` carry sentences, not JSON, and a sentence supplies
    none of the structural delimiters; without a sentence boundary the capture
    ran from the key to the end of the line, so ``medication: insulin. Please
    forward to the specialist.`` was stored as a 42-character "medication".
    A period only ends the value when whitespace or the end of the text follows
    it, so decimals (``3.5``), hostnames and addresses inside a value survive.
    """
    return re.compile(
        rf"""["']?\b(?:{stem})\b["']?\s*[:=]\s*["']?((?:[^"'|,;}}\n.]|\.(?!\s|$))+)""",
        re.IGNORECASE,
    )


_COMPILED: list[tuple[re.Pattern[str], str, Severity, str]] = [
    (_compile(stem), data_type, severity, advice)
    for stem, (data_type, severity, advice) in _SENSITIVE_KEYS.items()
]


class SensitiveKeyDetector(Detector):
    name = "keyname_detector"

    def detect(self, text: str) -> list[RawMatch]:
        matches: list[RawMatch] = []
        for pattern, data_type, severity, advice in _COMPILED:
            for m in pattern.finditer(text):
                value = m.group(1).strip().strip("\"'")
                value = _VALUE_TAIL_RE.sub("", value)
                if len(value) < 2 or _TRIVIAL_VALUE_RE.match(value):
                    continue
                if len(value) > _MAX_VALUE_LEN:
                    # Not a field value any more. Reporting it would put an
                    # unreadable span in the evidence and a phantom secret in
                    # the vault; the value detectors still cover this text.
                    continue
                matches.append(self._match(
                    data_type=data_type, severity=severity,
                    confidence=0.6, matched_value=value, recommendation=advice,
                ))
        return matches
