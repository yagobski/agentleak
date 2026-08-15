# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Shared test fixtures."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def _isolate_agentleak_home(tmp_path_factory):
    """Point the platform store at a throwaway dir so tests never touch
    the user's real ~/.agentleak database.
    """
    home = tmp_path_factory.mktemp("agentleak_home")
    os.environ["AGENTLEAK_HOME"] = str(home)
    yield


def authenticate(client, *, email: str = "tester@agentleak.local", password: str = "test-pass-123"):
    """Register (or log in) a user so ``client`` carries a session cookie."""
    creds = {"email": email, "password": password}
    r = client.post("/api/auth/register", json=creds)
    if r.status_code == 409:  # already registered in this DB
        r2 = client.post("/api/auth/login", json=creds)
        if r2.status_code not in (200, 201):
            raise RuntimeError(f"login failed: {r2.status_code} {r2.text}")
    return client


@pytest.fixture(scope="session")
def login():
    """Return the :func:`authenticate` helper (usable inside other fixtures)."""
    return authenticate

