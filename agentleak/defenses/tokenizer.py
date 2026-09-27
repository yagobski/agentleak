# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Stable pseudonyms for sensitive values, reversible only in memory.

Redaction removes a value, which is right for a log and wrong for a tool call
that needs to refer to the same customer twice: ``[REDACTED_SIN]`` in the
lookup and ``[REDACTED_SIN]`` in the update are indistinguishable, and the
second call fails for a reason nobody can see. A token keeps the reference and
drops the value: the same SIN becomes the same ``[[SIN:3f9a1c2e40]]`` every
time, so a downstream tool can match on it without ever holding it.

Tokens are a keyed HMAC of the type and value, so they cannot be reversed or
dictionary-attacked without the key. The key is random per process unless
``AGENTLEAK_TOKEN_KEY`` is set, which makes tokens stable across processes.

Reversal exists, and it is deliberately narrow: the token-to-value map lives in
this object's memory and nowhere else. The MCP proxy uses it to put the real
value back into a tool's response on its way to the agent that sent it. Nothing
is written to disk, because a file mapping tokens to values would be exactly
the leak this project exists to find.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from typing import Any

__all__ = ["Tokenizer", "TOKEN_RE"]

TOKEN_RE = re.compile(r"\[\[([A-Z][A-Z0-9_]*):([0-9a-f]{10})\]\]")
_KEY_ENV = "AGENTLEAK_TOKEN_KEY"


def _key_from_env() -> bytes | None:
    raw = os.environ.get(_KEY_ENV, "")
    return raw.encode("utf-8") if raw else None


class Tokenizer:
    """Deterministic, keyed pseudonyms with an in-memory reverse map."""

    def __init__(self, key: bytes | str | None = None) -> None:
        if isinstance(key, str):
            key = key.encode("utf-8")
        self._key = key or _key_from_env() or os.urandom(32)
        self._values: dict[str, str] = {}

    def token(self, value: str, data_type: str) -> str:
        """The pseudonym for *value*; the same input always gives the same token."""
        dtype = data_type.upper()
        digest = hmac.new(self._key, f"{dtype}\0{value}".encode(), hashlib.sha256).hexdigest()
        tok = f"[[{dtype}:{digest[:10]}]]"
        self._values[tok] = value
        return tok

    def restore(self, text: str) -> str:
        """Put back every token this tokenizer issued; leave any other alone."""
        if "[[" not in text:
            return text
        return TOKEN_RE.sub(lambda m: self._values.get(m.group(0), m.group(0)), text)

    def restore_obj(self, value: Any) -> Any:
        """:meth:`restore` over every string in a nested JSON value."""
        if isinstance(value, str):
            return self.restore(value)
        if isinstance(value, dict):
            return {k: self.restore_obj(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.restore_obj(v) for v in value]
        return value

    def __len__(self) -> int:
        return len(self._values)
