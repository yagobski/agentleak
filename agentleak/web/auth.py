# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Session authentication for the local AgentLeak platform.

Accounts and sessions live entirely in the local SQLite store (see
``agentleak.core.store``). A successful login issues an opaque, random session
token stored server-side and handed to the browser as an http-only cookie, so
no credentials or tokens are ever exposed to client-side JavaScript.
"""

from __future__ import annotations

import re
from typing import Any

# Name of the http-only cookie that carries the session token.
COOKIE_NAME = "agentleak_session"
COOKIE_MAX_AGE = 30 * 24 * 3600  # mirror Store.SESSION_TTL

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LEN = 8


def normalize_email(email: Any) -> str:
    return str(email or "").strip().lower()


def valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email))


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    """Client-safe projection of a stored user (never includes the hash)."""
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name") or user["email"].split("@")[0],
        "created_at": user.get("created_at"),
        "is_admin": bool(user.get("is_admin")),
    }


class LoginRateLimiter:
    """Small in-memory brute-force guard for the login endpoint.

    Allows at most ``max_attempts`` failed attempts per key (email) within
    ``window`` seconds. Successful logins reset the counter. Per-app-instance
    state — no external dependency, adequate for a single-process deployment;
    put a real WAF/rate limiter in front for multi-replica setups.
    """

    def __init__(self, *, max_attempts: int = 10, window: float = 300.0) -> None:
        self.max_attempts = max_attempts
        self.window = window
        self._attempts: dict[str, list[float]] = {}

    def allow(self, key: str, *, now: float | None = None) -> bool:
        import time

        ts = now if now is not None else time.time()
        attempts = [t for t in self._attempts.get(key, []) if ts - t < self.window]
        self._attempts[key] = attempts
        return len(attempts) < self.max_attempts

    def record_failure(self, key: str, *, now: float | None = None) -> None:
        import time

        ts = now if now is not None else time.time()
        self._attempts.setdefault(key, []).append(ts)

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)

    def hit(self, key: str, *, now: float | None = None) -> bool:
        """Convenience for generic (non-login) rate limiting: returns True and
        records the attempt if ``key`` is still under the limit, else False
        (and does not record) — call sites just do ``if not limiter.hit(k):
        raise 429``."""
        if not self.allow(key, now=now):
            return False
        self.record_failure(key, now=now)
        return True


# Generic alias — the class isn't login-specific (sliding-window counter per
# key); used for both login brute-force protection and agent-API throttling.
RateLimiter = LoginRateLimiter
