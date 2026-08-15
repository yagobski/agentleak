# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Technical secret detector: API keys, tokens, private keys, connection
strings, and password/secret assignments.

Leaked credentials are treated as the most severe class — a leaked key is
immediately actionable by an attacker — so most matches here are critical.
"""

from __future__ import annotations

import re

from ..core.detector import Detector, RawMatch, Severity

AWS_ACCESS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
GITHUB_TOKEN_RE = re.compile(r"\bgh[oprsu]_[A-Za-z0-9]{36}\b")
SLACK_TOKEN_RE = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")
STRIPE_KEY_RE = re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}\b")
# OpenAI / Anthropic keys use a hyphen separator (sk-..., sk-proj-..., sk-ant-...),
# which is distinct from Stripe's underscore form (sk_live_...). Agent runtimes
# routinely carry these in tool calls and env dumps, so treat them as critical.
LLM_API_KEY_RE = re.compile(
    r"\bsk-(?:proj|svcacct|admin|ant-api\d{2})?-?[A-Za-z0-9_-]{16,}\b"
)
# Google API key (Maps, Cloud, Gemini) — fixed AIza prefix + 35 url-safe chars.
GOOGLE_API_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
# Opaque `Authorization: Bearer <token>` values. JWTs are handled separately, so
# the JWT branch is skipped here to avoid double-reporting the same substring.
BEARER_TOKEN_RE = re.compile(r"(?i)\bbearer\s+([A-Za-z0-9._~+/=-]{16,})")
PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"
)
CONNECTION_STRING_RE = re.compile(
    r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqps?)://[^\s'\"]+"
)
# Generic ``password: ...`` / ``api_key = ...`` assignments. Broad, so lower
# confidence; the assigned value must be non-trivial.
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)\b"
    r"\s*[:=]\s*[\"']?([^\"'\s,}]{6,})"
)

# A captured "value" that is really a function call or attribute access is a
# reference, not a hardcoded secret — e.g. ``api_key = os.environ.get("KEY")``
# or ``token = settings.API_KEY``. Reading a credential from the environment is
# the *correct* pattern and must not be flagged. Matching one of these means the
# assignment does not embed a literal secret.
_SECRET_REFERENCE_RE = re.compile(
    r"""^(?:
        os\.environ|os\.getenv|getenv|environ|          # env reads
        .*\.get\(|.*\(|                                  # any function/method call
        (?:self|settings|config|cfg|conf|env|os|process)\.  # attribute lookups
    )""",
    re.IGNORECASE | re.VERBOSE,
)

# An ALL-CAPS identifier (``API_KEY``, ``ACCESS_TOKEN``) assigned as a value is a
# constant/variable reference — ``api_key=API_KEY`` — not an embedded secret.
# Real inline secrets are quoted literals or mixed-case tokens; a genuinely
# random ALL-CAPS token is still caught by the entropy tier.
_CONSTANT_REFERENCE_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")


class SecretsDetector(Detector):
    name = "secrets_detector"

    def detect(self, text: str) -> list[RawMatch]:
        matches: list[RawMatch] = []

        for m in PRIVATE_KEY_RE.finditer(text):
            matches.append(self._match(
                data_type="private_key", severity=Severity.CRITICAL, confidence=0.99,
                matched_value=m.group(0),
                recommendation="Rotate the key immediately; private keys must never enter agent channels.",
            ))

        for m in AWS_ACCESS_KEY_RE.finditer(text):
            matches.append(self._match(
                data_type="aws_access_key", severity=Severity.CRITICAL, confidence=0.97,
                matched_value=m.group(0),
                recommendation="Rotate the AWS key and inject credentials at the runtime boundary only.",
            ))

        for m in GITHUB_TOKEN_RE.finditer(text):
            matches.append(self._match(
                data_type="github_token", severity=Severity.CRITICAL, confidence=0.95,
                matched_value=m.group(0),
                recommendation="Revoke the GitHub token; do not pass tokens through prompts or memory.",
            ))

        for m in SLACK_TOKEN_RE.finditer(text):
            matches.append(self._match(
                data_type="slack_token", severity=Severity.CRITICAL, confidence=0.9,
                matched_value=m.group(0),
                recommendation="Revoke the Slack token; keep secrets out of inter-agent messages.",
            ))

        for m in STRIPE_KEY_RE.finditer(text):
            matches.append(self._match(
                data_type="stripe_key", severity=Severity.CRITICAL, confidence=0.95,
                matched_value=m.group(0),
                recommendation="Rotate the Stripe key; never expose payment provider secrets to agents.",
            ))

        for m in LLM_API_KEY_RE.finditer(text):
            matches.append(self._match(
                data_type="llm_api_key", severity=Severity.CRITICAL, confidence=0.95,
                matched_value=m.group(0),
                recommendation="Rotate the model-provider key; inject it at the runtime boundary, never in prompts or memory.",
            ))

        for m in GOOGLE_API_KEY_RE.finditer(text):
            matches.append(self._match(
                data_type="google_api_key", severity=Severity.CRITICAL, confidence=0.93,
                matched_value=m.group(0),
                recommendation="Rotate the Google API key and restrict it; keep cloud keys out of agent channels.",
            ))

        for m in JWT_RE.finditer(text):
            matches.append(self._match(
                data_type="jwt", severity=Severity.HIGH, confidence=0.85,
                matched_value=m.group(0),
                recommendation="Do not store or forward raw JWTs; they may carry identity and claims.",
            ))

        for m in BEARER_TOKEN_RE.finditer(text):
            token = m.group(1)
            # JWTs after `Bearer` are already covered by JWT_RE above.
            if token.startswith("eyJ"):
                continue
            matches.append(self._match(
                data_type="bearer_token", severity=Severity.HIGH, confidence=0.8,
                matched_value=token,
                recommendation="Strip Authorization bearer tokens from traces; they grant live access.",
            ))

        for m in CONNECTION_STRING_RE.finditer(text):
            value = m.group(0)
            has_creds = "@" in value and "://" in value and ":" in value.split("://", 1)[1].split("@")[0]
            matches.append(self._match(
                data_type="connection_string",
                severity=Severity.CRITICAL if has_creds else Severity.HIGH,
                confidence=0.9 if has_creds else 0.75,
                matched_value=value,
                recommendation="Strip database/connection strings (and embedded credentials) from traces.",
            ))

        for m in SECRET_ASSIGNMENT_RE.finditer(text):
            value = m.group(2)
            # Skip obvious placeholders to reduce false positives.
            if value.lower() in {"none", "null", "true", "false", "redacted", "xxxxxx", "******"}:
                continue
            # Skip references (env reads, function calls, attribute lookups,
            # ALL-CAPS constants): they point at a secret, they don't embed one.
            if _SECRET_REFERENCE_RE.match(value) or _CONSTANT_REFERENCE_RE.match(value):
                continue
            matches.append(self._match(
                data_type="secret_assignment", severity=Severity.HIGH, confidence=0.65,
                matched_value=value,
                recommendation="Remove inline secret assignments from agent payloads and logs.",
            ))

        return matches
