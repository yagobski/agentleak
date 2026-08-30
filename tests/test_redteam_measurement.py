# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""A scripted red-team run must not read as a verdict on the caller's agent.

Running the offline baseline returns ASR 1.0 across every family, which is
correct — the scripted target leaks by construction, so a perfect score means
the detectors saw every planted leak. Read without that context, "100% of
attacks succeeded" is a devastating and entirely false statement about an agent
that was never executed.

This project's own roadmap guardrail says it directly: never display an
integrity result as detector or agent accuracy, and distinguish
`fixture_integrity` from `policy_outcome`. So the response says which it is.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agentleak.web.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTLEAK_HOME", str(tmp_path))
    monkeypatch.setenv("AGENTLEAK_LOCAL_MODE", "1")
    monkeypatch.delenv("AGENTLEAK_PUBLIC_MODE", raising=False)
    return TestClient(create_app(serve_ui=False))


@pytest.fixture
def project(client):
    created = client.post("/api/projects", json={"name": "rt", "agent_type": "generic"})
    assert created.status_code in (200, 201)
    return created.json()["id"]


def test_a_scripted_run_declares_what_it_measured(client, project) -> None:
    response = client.post(f"/api/projects/{project}/redteam",
                           json={"preset": "privacy_core", "strategy": "basic"})
    assert response.status_code == 200
    body = response.json()
    assert body["live"] is False

    measurement = body["measurement"]
    assert measurement["category"] == "fixture_integrity"
    assert "not your" in measurement["means"] or "not executed" in measurement["means"]
    assert "scripted" in measurement["target"]


def test_the_caveat_names_the_thing_that_was_actually_attacked(client, project) -> None:
    """The reader has to learn their own agent was never run."""
    body = client.post(f"/api/projects/{project}/redteam",
                       json={"preset": "privacy_core", "strategy": "basic"}).json()
    assert "leaks by design" in body["measurement"]["target"]


def test_the_metrics_are_still_reported(client, project) -> None:
    """Labelling the measurement must not hide it — the numbers are useful, they
    are just about the fixture.
    """
    body = client.post(f"/api/projects/{project}/redteam",
                       json={"preset": "privacy_core", "strategy": "basic"}).json()
    assert "overall_asr" in body["metrics"]
    assert body["scenarios_run"] > 0
