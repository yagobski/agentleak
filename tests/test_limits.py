"""Tests for public-SaaS limits config and helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from agentleak.web.limits import (
    Limits,
    client_ip,
    month_start,
    next_month_start,
)


def test_defaults_are_unlimited_local(monkeypatch):
    for var in (
        "AGENTLEAK_PUBLIC_MODE", "AGENTLEAK_FREE_MONTHLY_QUOTA",
        "AGENTLEAK_REGISTER_IP_LIMIT", "AGENTLEAK_IP_RATE_LIMIT",
        "AGENTLEAK_FORCE_BYOK", "AGENTLEAK_COOKIE_SECURE",
    ):
        monkeypatch.delenv(var, raising=False)
    lim = Limits.from_env()
    assert lim.public_mode is False
    assert lim.free_monthly_quota == 0  # unlimited
    assert lim.register_per_ip_hour == 0
    assert lim.global_ip_per_minute == 0
    assert lim.force_byok is False
    assert lim.cookie_secure is False


def test_public_mode_flips_safe_defaults(monkeypatch):
    for var in (
        "AGENTLEAK_FREE_MONTHLY_QUOTA", "AGENTLEAK_REGISTER_IP_LIMIT",
        "AGENTLEAK_IP_RATE_LIMIT", "AGENTLEAK_FORCE_BYOK", "AGENTLEAK_COOKIE_SECURE",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("AGENTLEAK_PUBLIC_MODE", "1")
    lim = Limits.from_env()
    assert lim.public_mode is True
    assert lim.free_monthly_quota == 1000
    assert lim.register_per_ip_hour == 10
    assert lim.global_ip_per_minute == 240
    assert lim.force_byok is True
    assert lim.cookie_secure is True


def test_explicit_env_overrides_public_defaults(monkeypatch):
    monkeypatch.setenv("AGENTLEAK_PUBLIC_MODE", "1")
    monkeypatch.setenv("AGENTLEAK_FREE_MONTHLY_QUOTA", "50")
    monkeypatch.setenv("AGENTLEAK_FORCE_BYOK", "0")
    lim = Limits.from_env()
    assert lim.free_monthly_quota == 50
    assert lim.force_byok is False


def test_month_boundaries():
    # 15 Jan 2026 12:34 UTC → window [1 Jan, 1 Feb).
    now = datetime(2026, 1, 15, 12, 34, tzinfo=timezone.utc).timestamp()
    assert month_start(now) == datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    assert next_month_start(now) == datetime(2026, 2, 1, tzinfo=timezone.utc).timestamp()


def test_month_boundary_year_rollover():
    now = datetime(2026, 12, 20, tzinfo=timezone.utc).timestamp()
    assert next_month_start(now) == datetime(2027, 1, 1, tzinfo=timezone.utc).timestamp()


def test_client_ip_prefers_forwarded_for():
    assert client_ip({"x-forwarded-for": "203.0.113.7, 10.0.0.1"}, "10.0.0.1") == "203.0.113.7"
    assert client_ip({}, "198.51.100.2") == "198.51.100.2"
    assert client_ip({}, "") == "unknown"
