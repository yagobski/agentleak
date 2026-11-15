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


# ----------------------------------------------------------------------
# QA-05: /llms.txt and docs/mcp.md quoted 283 bundled scenarios; 266 ship
# ----------------------------------------------------------------------


def test_served_docs_quote_the_scenario_count_that_ships(tmp_path) -> None:
    import re
    from pathlib import Path

    client = TestClient(create_app(store=Store(str(tmp_path / "qa.db"))))
    total = client.get("/api/meta").json()["scenarios"]["total"]
    texts = {
        "/llms.txt": client.get("/llms.txt").text,
        "/llms-full.txt": client.get("/llms-full.txt").text,
        "/agents.md": client.get("/agents.md").text,
        "docs/mcp.md": (Path(__file__).parents[1] / "docs" / "mcp.md").read_text("utf-8"),
    }
    for where, text in texts.items():
        for n in re.findall(r"(\d+) (?:bundled )?scenarios bundled|(\d+) bundled scenarios", text):
            quoted = int(n[0] or n[1])
            assert quoted == total, f"{where} quotes {quoted} bundled scenarios, {total} ship"


# ----------------------------------------------------------------------
# QA-06: malformed input produced 500s, and a bad PATCH bricked a project
# ----------------------------------------------------------------------


@pytest.fixture()
def one_user(tmp_path):
    store = Store(str(tmp_path / "qa.db"))
    client = TestClient(create_app(store=store), raise_server_exceptions=False)
    client.post("/api/auth/register", json={"email": "q@example.test", "password": "q-pass-12345"})
    pid = client.post("/api/projects", json={"name": "P"}).json()["id"]
    key = client.post(f"/api/projects/{pid}/api-key").json()["api_key"]
    return client, pid, key, store


@pytest.mark.parametrize("config", ["bad", [1], {"vault": "x"}, {"vault": {"mode": "explicit", "levels": 3}}])
def test_patch_rejects_unloadable_config_and_project_keeps_working(one_user, config) -> None:
    client, pid, _, _ = one_user
    r = client.patch(f"/api/projects/{pid}", json={"config": config})
    assert r.status_code == 400
    assert client.post(f"/api/projects/{pid}/runs", json={"scenario_id": "hr_clean_case"}).status_code == 200
    assert client.post(f"/api/projects/{pid}/api-key").status_code == 200


def test_project_stored_with_non_object_config_still_loads(one_user) -> None:
    client, pid, _, store = one_user
    with store._conn() as conn:  # simulate a row written by an older build
        conn.execute("UPDATE projects SET config = ? WHERE id = ?", ('"bad"', pid))
    assert client.get(f"/api/projects/{pid}").status_code == 200
    assert client.post(f"/api/projects/{pid}/runs", json={"scenario_id": "hr_clean_case"}).status_code == 200


@pytest.mark.parametrize(
    "path, body",
    [
        ("/api/render/html", {"report": {"channel_risks": "x"}}),
        ("/api/render/markdown", {"report": {}}),
        ("/api/compare", {"a": [], "b": {}}),
        ("/api/scenarios", {"data": {"objective": "x", "private_vault": {"records": []}}}),
        ("/api/scenarios", {"data": {"objective": {}, "private_vault": []}}),
        ("/api/scenarios", {"data": {"source_text": 5, "pii_annotations": 3}}),
        ("/api/analyze", {"trace": [1]}),
        ("/api/analyze", {"trace": {"events": "x"}}),
        ("/api/analyze", {"trace": {"events": [1]}}),
    ],
)
def test_malformed_session_input_is_a_4xx(one_user, path, body) -> None:
    client = one_user[0]
    r = client.post(path, json=body)
    assert 400 <= r.status_code < 500, (path, r.status_code, r.text[:200])


def test_redteam_rejects_non_integer_n(one_user) -> None:
    client, pid, _, _ = one_user
    assert client.post(f"/api/projects/{pid}/redteam", json={"n": "abc"}).status_code == 400


@pytest.mark.parametrize("path", ["/api/selftest", "/api/agent/improve"])
@pytest.mark.parametrize("trace", [[1], {"events": 3}, {"events": ["x"]}])
def test_malformed_selftest_trace_is_a_400(one_user, path, trace) -> None:
    client, _, key, _ = one_user
    r = client.post(path, json={"trace": trace}, headers={"x-agentleak-key": key})
    assert r.status_code == 400, r.text[:200]


# ----------------------------------------------------------------------
# QA-07: a custom detector regex could pin a server worker for hours
# ----------------------------------------------------------------------


def test_nested_repeat_custom_detector_is_refused(one_user) -> None:
    import time

    client, pid, key, _ = one_user
    evil = [{"name": "x", "pattern": "(a+)+$"}]
    trace = {"events": [{"channel": "log", "content": "a" * 40 + "!"}]}
    start = time.monotonic()
    assert client.post("/api/analyze", json={"trace": trace, "custom_detectors": evil}).status_code == 400
    assert client.post(
        "/api/selftest", json={"trace": trace, "custom_detectors": evil},
        headers={"x-agentleak-key": key},
    ).status_code == 400
    assert client.patch(
        f"/api/projects/{pid}", json={"config": {"custom_detectors": evil}}
    ).status_code == 400
    assert time.monotonic() - start < 5
    ok = [{"name": "emp", "pattern": r"\bEMP-\d{6}\b"}]
    assert client.post("/api/analyze", json={"trace": trace, "custom_detectors": ok}).status_code == 200
