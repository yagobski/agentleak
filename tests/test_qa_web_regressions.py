# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Web API regressions from the QA pass (see QA-REPORT.md). Synthetic data only."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from agentleak.core.store import Store  # noqa: E402
from agentleak.web import create_app  # noqa: E402

_TRACE = {
    "events": [
        {"channel": "tool_response", "content": {"patient": "Ada Quill", "ssn": "123-45-6789"}},
        {"channel": "log", "content": "Patient Ada Quill SSN 123-45-6789"},
    ]
}


@pytest.fixture()
def two_users(tmp_path):
    app = create_app(store=Store(str(tmp_path / "qa.db")))
    alice, bob, anon = TestClient(app), TestClient(app), TestClient(app)
    alice.post("/api/auth/register", json={"email": "alice@example.test", "password": "alice-pass-123"})
    bob.post("/api/auth/register", json={"email": "bob@example.test", "password": "bob-pass-12345"})
    sid = alice.post("/api/scenarios", json={"data": _TRACE, "name": "private"}).json()["id"]
    pid_b = bob.post("/api/projects", json={"name": "B"}).json()["id"]
    key_b = bob.post(f"/api/projects/{pid_b}/api-key").json()["api_key"]
    return {"alice": alice, "bob": bob, "anon": anon, "sid": sid, "pid_b": pid_b, "key_b": key_b}


# ----------------------------------------------------------------------
# QA-03: another account's stored scenario was reachable by id through every
# endpoint that accepts ``scenario_id``
# ----------------------------------------------------------------------


def test_owner_can_still_analyze_own_stored_scenario(two_users) -> None:
    r = two_users["alice"].post("/api/analyze", json={"scenario_id": two_users["sid"]})
    assert r.status_code == 200
    assert r.json()["findings"]


@pytest.mark.parametrize(
    "who, method, path",
    [
        ("bob", "post", "/api/analyze"),
        ("bob", "post", "/api/report/markdown"),
        ("bob", "post", "/api/projects/{pid_b}/runs"),
        ("bob", "post", "/api/projects/{pid_b}/execute"),
        ("anon", "post", "/api/selftest"),
        ("anon", "post", "/api/agent/improve"),
    ],
)
def test_foreign_scenario_id_is_not_resolved(two_users, who, method, path) -> None:
    client = two_users[who]
    url = path.format(pid_b=two_users["pid_b"])
    body = {"scenario_id": two_users["sid"], "mode": "scripted"}
    r = getattr(client, method)(url, json=body, headers={"x-agentleak-key": two_users["key_b"]})
    assert r.status_code in (400, 404), (url, r.status_code, r.text[:200])
    assert "Ada" not in r.text and "12*" not in r.text


def test_publish_refuses_an_ownerless_project(tmp_path) -> None:
    store = Store(str(tmp_path / "qa.db"))
    legacy = store.create_project("legacy")  # no owner, as before accounts existed
    client = TestClient(create_app(store=store))
    client.post("/api/auth/register", json={"email": "eve@example.test", "password": "eve-pass-1234"})
    r = client.post(f"/api/projects/{legacy['id']}/publish", json={"slug": "taken-over"})
    assert r.status_code == 404
    assert store.project_by_slug("taken-over") is None
