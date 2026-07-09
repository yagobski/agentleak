"""Public-SaaS runtime limits and configuration.

AgentLeak runs in two shapes from the same code:

* **Local / self-hosted** (default) — no quotas, no per-IP throttling, and the
  process may use an ``OPENROUTER_API_KEY`` from its environment. This keeps the
  ``python -m agentleak serve`` developer loop frictionless.
* **Public mode** (``AGENTLEAK_PUBLIC_MODE=1``) — the hosted, free-for-agents
  deployment. Turns on a monthly free-tier quota, per-IP anti-abuse throttling,
  secure cookies, and BYOK enforcement (the platform never spends its own money
  on an agent's LLM calls).

Every knob is individually overridable via an environment variable so an
operator can tune a public deployment without a code change.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Limits:
    """Resolved runtime limits for the current process."""

    public_mode: bool
    #: Metered actions allowed per calendar month per account. 0 = unlimited.
    free_monthly_quota: int
    #: New registrations allowed per client IP per hour. 0 = unlimited.
    register_per_ip_hour: int
    #: Requests allowed per client IP per minute (global DoS guard). 0 = off.
    global_ip_per_minute: int
    #: When true, ignore any process-level LLM key so free runs are BYOK-only.
    force_byok: bool
    #: Send the session cookie with the Secure attribute (HTTPS only).
    cookie_secure: bool

    @classmethod
    def from_env(cls) -> Limits:
        public = _env_flag("AGENTLEAK_PUBLIC_MODE", False)
        # Public mode flips the sensible-for-a-hosted-service defaults on; each
        # can still be overridden explicitly.
        return cls(
            public_mode=public,
            free_monthly_quota=_env_int(
                "AGENTLEAK_FREE_MONTHLY_QUOTA", 1000 if public else 0
            ),
            register_per_ip_hour=_env_int(
                "AGENTLEAK_REGISTER_IP_LIMIT", 10 if public else 0
            ),
            global_ip_per_minute=_env_int(
                "AGENTLEAK_IP_RATE_LIMIT", 240 if public else 0
            ),
            force_byok=_env_flag("AGENTLEAK_FORCE_BYOK", public),
            cookie_secure=_env_flag("AGENTLEAK_COOKIE_SECURE", public),
        )


def month_start(now: float | None = None) -> float:
    """Unix timestamp for 00:00 UTC on the first day of the current month."""
    dt = datetime.fromtimestamp(now if now is not None else time.time(), tz=timezone.utc)
    first = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return first.timestamp()


def next_month_start(now: float | None = None) -> float:
    """Unix timestamp for when the monthly quota window resets."""
    dt = datetime.fromtimestamp(now if now is not None else time.time(), tz=timezone.utc)
    if dt.month == 12:
        nxt = dt.replace(year=dt.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        nxt = dt.replace(month=dt.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return nxt.timestamp()


def client_ip(headers: dict[str, str], fallback: str) -> str:
    """Best-effort client IP behind a trusted reverse proxy.

    Reads the left-most hop of ``X-Forwarded-For`` (set by Caddy/nginx in the
    hosted deployment); falls back to the direct socket peer otherwise.
    """
    xff = headers.get("x-forwarded-for") or headers.get("X-Forwarded-For")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    return fallback or "unknown"
