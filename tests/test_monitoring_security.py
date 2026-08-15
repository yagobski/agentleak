# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Tests for admin monitoring (runs/consumption/results per project), the
public agent-discovery surface, and the security hardening added alongside
the SaaS admin console: disabled-owner API lockout, per-key agent rate
limiting, and the code-scanner's defensive size caps."""

from __future__ import annotations

import io
import zipfile

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentleak import __version__  # noqa: E402
from agentleak.core.agentcard import parse_agent_card, platform_card  # noqa: E402
from agentleak.core.codescan import (  # noqa: E402
    MAX_ZIP_UNCOMPRESSED_BYTES,
    fetch_github_repo,
    scan_zip_bytes,
)
from agentleak.core.store import Store  # noqa: E402
from agentleak.web.app import create_app  # noqa: E402
from agentleak.web.auth import RateLimiter  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    return create_app(store=Store(str(tmp_path / "monitor.db")))


def _register(client: TestClient, email: str, password: str = "test-pass-123") -> TestClient:
    r = client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return client


LEAKY_TRACE = {
    "run_id": "run_x",
    "agent_name": "monitored-bot",
    "events": [
        {"channel": "tool_call", "source": "agent", "target": "crm",
         "content": {"customer_email": "jane@acme.com"}},
        {"channel": "final_output", "content": "All set!"},
    ],
}


# =========================================================================
# Agent discoverability
# =========================================================================
def test_platform_agent_card_is_public_and_valid():
    card_dict = platform_card("1.2.3").to_dict()
    card = parse_agent_card(card_dict)  # must round-trip through the parser
    assert card.name == "agentleak"
    assert card.agent_protocol_version == "a2a-v1"
    assert "privacy_selftest" in card.capabilities
    assert "/api/selftest" in card.endpoints
    assert card.validate() == []


def test_well_known_agent_card_endpoint_unauthenticated(app):
    anon = TestClient(app)
    r = anon.get("/.well-known/agent-card.json")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "agentleak"
    assert body["version"] == __version__
    # Reachable by the platform's OWN card-fetching helper.
    parsed = parse_agent_card(body)
    assert parsed.is_valid


def test_meta_advertises_agent_api_unauthenticated(app):
    r = TestClient(app).get("/api/meta")
    assert r.status_code == 200
    body = r.json()
    assert body["agent_card_url"] == "/.well-known/agent-card.json"
    assert "register" in body["agent_api"]
    assert "improve" in body["agent_api"]


# =========================================================================
# Admin monitoring: runs, consumption, results
# =========================================================================
def _project_with_key(client: TestClient, name: str) -> tuple[str, str]:
    pid = client.post("/api/projects", json={"name": name}).json()["id"]
    key = client.post(f"/api/projects/{pid}/api-key").json()["api_key"]
    return pid, key


def test_admin_usage_tracks_runs_and_api_consumption(app):
    admin = _register(TestClient(app), "owner@x.com")
    _, key = _project_with_key(admin, "Monitored Bot")
    agent = TestClient(app)
    headers = {"X-AgentLeak-Key": key}

    agent.post("/api/agent/register", json={"agent_card": {
        "name": "monitored-bot", "capabilities": ["ticket_triage"],
    }}, headers=headers)
    agent.post("/api/agent/improve", json={"trace": LEAKY_TRACE}, headers=headers)
    agent.get("/api/agent/status", headers=headers)

    usage = admin.get("/api/admin/usage").json()
    projects = {p["name"]: p for p in usage["projects"]}
    mon = projects["Monitored Bot"]
    assert mon["run_count"] == 1  # the improve() selftest saved one run
    assert mon["owner_email"] == "owner@x.com"
    # register + improve (which itself triggers a nested selftest recording)
    # + status = at least 3 recorded API hits.
    assert mon["api_call_count"] >= 3
    assert mon["last_run_at"] is not None
    assert mon["last_api_call_at"] is not None

    # Daily series covers 14 days and today shows the activity above.
    daily = usage["daily"]
    assert len(daily) == 14
    assert daily[-1]["runs"] >= 1
    assert daily[-1]["api_calls"] >= 3
    assert daily[-1]["blocked_runs"] >= 1
    assert "code_scans" in daily[-1]

    endpoints = {item["endpoint"]: item for item in usage["endpoints"]}
    assert endpoints["/api/agent/status"]["count"] >= 1
    assert endpoints["/api/agent/status"]["projects"] == 1

    overview = admin.get("/api/admin/overview").json()
    assert overview["api_calls_total"] >= 3
    assert overview["api_calls_24h"] >= 3
    assert overview["runs_24h"] == 1
    assert overview["blocked_24h"] == 1
    assert overview["active_projects_24h"] == 1
    assert overview["avg_privacy_score"] is not None


def test_admin_usage_forbidden_for_members(app):
    _register(TestClient(app), "owner@x.com")
    member = _register(TestClient(app), "member@x.com")
    assert member.get("/api/admin/usage").status_code == 403


def test_admin_usage_empty_platform(app):
    admin = _register(TestClient(app), "owner@x.com")
    usage = admin.get("/api/admin/usage").json()
    assert usage["projects"] == []
    assert usage["endpoints"] == []
    assert len(usage["daily"]) == 14
    assert all(
        d["runs"] == 0 and d["api_calls"] == 0 and d["blocked_runs"] == 0
        and d["code_scans"] == 0
        for d in usage["daily"]
    )


# =========================================================================
# Security: disabling an owner revokes their agents' API-key access too
# =========================================================================
def test_disabling_owner_blocks_agent_api_access(app):
    admin = _register(TestClient(app), "owner@x.com")
    member = _register(TestClient(app), "member@x.com")
    uid = member.get("/api/auth/me").json()["id"]
    _, key = _project_with_key(member, "Member Bot")
    headers = {"X-AgentLeak-Key": key}

    # Works while the account is active.
    assert member.get("/api/agent/status", headers=headers).status_code == 200

    admin.patch(f"/api/admin/users/{uid}", json={"disabled": True})

    # The API key must stop working the instant the owner is disabled —
    # not just the browser session.
    r = member.get("/api/agent/status", headers=headers)
    assert r.status_code == 401

    r = member.post("/api/selftest", json={"api_key": key, "trace": LEAKY_TRACE})
    assert r.status_code == 401

    # Re-enabling restores access.
    admin.patch(f"/api/admin/users/{uid}", json={"disabled": False})
    assert member.get("/api/agent/status", headers=headers).status_code == 200


# =========================================================================
# Security: per-API-key rate limiting on the agent surface
# =========================================================================
def test_agent_endpoint_rate_limited_per_key(app):
    admin = _register(TestClient(app), "owner@x.com")
    _, key = _project_with_key(admin, "Busy Bot")
    agent = TestClient(app)
    headers = {"X-AgentLeak-Key": key}

    ok = 0
    limited = 0
    for _ in range(130):
        r = agent.get("/api/agent/status", headers=headers)
        if r.status_code == 200:
            ok += 1
        elif r.status_code == 429:
            limited += 1
        else:
            raise AssertionError(f"unexpected status {r.status_code}: {r.text}")
    assert ok == 120  # the configured window budget
    assert limited > 0


def test_rate_limiter_hit_convenience_method():
    limiter = RateLimiter(max_attempts=2, window=60)
    assert limiter.hit("k", now=0.0) is True
    assert limiter.hit("k", now=0.0) is True
    assert limiter.hit("k", now=0.0) is False  # third hit in the window fails
    assert limiter.hit("k", now=61.0) is True  # window has rolled over


# =========================================================================
# Security: static-scanner defensive size caps
# =========================================================================
def _make_zip(entries: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_zip_bomb_declared_size_rejected():
    """A zip whose declared uncompressed size exceeds the cap is rejected
    before any decompression happens."""
    huge = "A" * (MAX_ZIP_UNCOMPRESSED_BYTES + 1)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("repo-main/big.py", huge)
    with pytest.raises(ValueError, match="zip-bomb guard"):
        scan_zip_bytes(buf.getvalue())


def test_normal_zip_still_scans_fine():
    blob = _make_zip({"repo-main/agent.py": 'x = "hello world"\n'})
    result = scan_zip_bytes(blob)
    assert result.files_scanned == 1


def test_github_fetch_enforces_download_cap(monkeypatch):
    """fetch_github_repo aborts a huge stream instead of buffering it all."""
    import agentleak.core.codescan as codescan

    class FakeResp:
        def __init__(self, total_bytes: int) -> None:
            self.remaining = total_bytes
            self.chunk = b"A" * (1024 * 1024)

        def read(self, n: int) -> bytes:
            if self.remaining <= 0:
                return b""
            take = min(n, self.remaining, len(self.chunk))
            self.remaining -= take
            return self.chunk[:take]

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        codescan.urllib.request, "urlopen",
        lambda req, timeout=30: FakeResp(codescan.MAX_GITHUB_DOWNLOAD_BYTES + 5 * 1024 * 1024),
    )
    with pytest.raises(ValueError, match="download limit"):
        fetch_github_repo("acme/huge-repo")


def test_github_fetch_within_cap_succeeds(monkeypatch):
    import agentleak.core.codescan as codescan

    class FakeResp:
        def __init__(self, data: bytes) -> None:
            self.data = data
            self.pos = 0

        def read(self, n: int) -> bytes:
            chunk = self.data[self.pos:self.pos + n]
            self.pos += len(chunk)
            return chunk

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    payload = b"small archive bytes"
    monkeypatch.setattr(codescan.urllib.request, "urlopen", lambda req, timeout=30: FakeResp(payload))
    assert fetch_github_repo("acme/small-repo") == payload
