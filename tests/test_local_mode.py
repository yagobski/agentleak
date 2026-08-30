# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""A loopback install should not open by asking for an email address.

`agentleak serve` presented a sign-in wall on 127.0.0.1, directly under the
footer that says "100% local". The workspace belongs to whoever is at the
machine; requiring an account to reach it is ceremony that contradicts the
product's first claim.

`--local` removes it. That makes these tests the most safety-sensitive in the
suite, because the feature is *an unauthenticated web application*, and the
whole design rests on one property: **it can only ever listen on loopback.**
Three independent gates enforce it — the CLI flag, the environment resolution,
and `run_server` itself — because the cost of a single missed check is a
dashboard on a routable address.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agentleak.cli import _is_loopback_host
from agentleak.web.app import create_app, is_loopback, run_server
from agentleak.web.limits import Limits


@pytest.fixture
def local_client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTLEAK_LOCAL_MODE", "1")
    monkeypatch.setenv("AGENTLEAK_HOME", str(tmp_path))
    monkeypatch.delenv("AGENTLEAK_PUBLIC_MODE", raising=False)
    return TestClient(create_app(serve_ui=False))


@pytest.fixture
def account_client(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENTLEAK_LOCAL_MODE", raising=False)
    monkeypatch.setenv("AGENTLEAK_HOME", str(tmp_path))
    return TestClient(create_app(serve_ui=False))


# ----------------------------------------------------------------------
# The safety property: loopback only, three gates
# ----------------------------------------------------------------------
@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "10.0.0.5", "example.com", "::"])
def test_run_server_refuses_a_routable_bind_in_local_mode(host, monkeypatch) -> None:
    """The last gate. The environment variable can be set directly, bypassing
    the CLI, so the server itself has to refuse.
    """
    monkeypatch.setenv("AGENTLEAK_LOCAL_MODE", "1")
    with pytest.raises(RuntimeError, match="Refusing to bind local mode"):
        run_server(host=host, open_browser=False)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "[::1]", "LOCALHOST"])
def test_loopback_addresses_are_recognised(host) -> None:
    assert is_loopback(host)
    assert _is_loopback_host(host)


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "example.com", "127.0.0.1.evil.com"])
def test_non_loopback_addresses_are_rejected(host) -> None:
    """`127.0.0.1.evil.com` is the one that matters: a substring check would
    have let it through.
    """
    assert not is_loopback(host)
    assert not _is_loopback_host(host)


def test_local_and_public_mode_cannot_coexist(monkeypatch) -> None:
    """Public mode is a hosted multi-account service and local mode is an
    unauthenticated workspace. Guessing which one was meant is not an option.
    """
    monkeypatch.setenv("AGENTLEAK_LOCAL_MODE", "1")
    monkeypatch.setenv("AGENTLEAK_PUBLIC_MODE", "1")
    with pytest.raises(RuntimeError, match="mutually exclusive"):
        Limits.from_env()


def test_local_mode_is_off_unless_asked_for(monkeypatch) -> None:
    monkeypatch.delenv("AGENTLEAK_LOCAL_MODE", raising=False)
    monkeypatch.delenv("AGENTLEAK_PUBLIC_MODE", raising=False)
    assert Limits.from_env().local_mode is False


# ----------------------------------------------------------------------
# What it actually does
# ----------------------------------------------------------------------
def test_the_workspace_is_reachable_without_signing_in(local_client) -> None:
    response = local_client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "owner@localhost"


def test_the_local_owner_is_stable_across_requests(local_client) -> None:
    """One workspace, not a new account per call."""
    first = local_client.get("/api/auth/me").json()["id"]
    second = local_client.get("/api/auth/me").json()["id"]
    assert first == second


def test_projects_work_without_a_session(local_client) -> None:
    created = local_client.post("/api/projects", json={"name": "local-agent"})
    assert created.status_code in (200, 201)
    listed = local_client.get("/api/projects")
    assert listed.status_code == 200
    assert [p["name"] for p in listed.json()] == ["local-agent"]


def test_the_local_owner_owns_the_deployment(local_client) -> None:
    """First account in a fresh database, so the console is reachable — the
    point of a single-user install.
    """
    assert local_client.get("/api/auth/me").json()["is_admin"] is True


# ----------------------------------------------------------------------
# Account mode is untouched
# ----------------------------------------------------------------------
def test_without_local_mode_authentication_is_still_required(account_client) -> None:
    """The regression that would matter most: upgrading must not silently
    remove the sign-in from an existing deployment.
    """
    assert account_client.get("/api/auth/me").status_code == 401
    assert account_client.get("/api/projects").status_code == 401


def test_account_mode_still_registers_and_signs_in(account_client) -> None:
    registered = account_client.post(
        "/api/auth/register",
        json={"email": "someone@example.com", "password": "TestPassw0rd!2026"},
    )
    assert registered.status_code == 200
    assert account_client.get("/api/auth/me").status_code == 200
