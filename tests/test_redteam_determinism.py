# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""A scripted red-team campaign gives the same answer every time.

It did not. The attack classes were drawn from an unseeded ``random.Random``
and the vault from the process-wide ``random`` module and ``secrets``, so one
request scored a mean RI of 1.0, the next 0.9758, and a single attack class
produced 10, 11 or 12 findings. A number that moves on its own cannot gate CI.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agentleak.generators.scenario_gen import ScenarioGenerator
from agentleak.generators.vault import VaultGenerator
from agentleak.web.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTLEAK_HOME", str(tmp_path))
    monkeypatch.setenv("AGENTLEAK_LOCAL_MODE", "1")
    monkeypatch.delenv("AGENTLEAK_PUBLIC_MODE", raising=False)
    return TestClient(create_app(serve_ui=False))


def _campaign(client, **extra):
    pid = client.post("/api/projects", json={"name": "rt", "agent_type": "generic"}).json()["id"]
    body = client.post(f"/api/projects/{pid}/redteam",
                       json={"preset": "privacy_core", "strategy": "basic", **extra}).json()
    return body, [(a["attack_class_id"], a["risk_index"], a["leaked_types"]) for a in body["attacks"]]


def test_same_request_same_campaign(client):
    first, a = _campaign(client)
    for _ in range(4):
        again, b = _campaign(client)
        assert b == a
        assert again["metrics"] == first["metrics"]


def test_seed_is_reported_and_changes_the_sample(client):
    body, a = _campaign(client, seed=0)
    assert body["seed"] == 0
    _, b = _campaign(client, seed=1)
    assert a != b


def test_vault_is_reproducible_from_a_seed():
    assert VaultGenerator(seed=7).generate("finance").to_dict() == \
        VaultGenerator(seed=7).generate("finance").to_dict()
    assert VaultGenerator(seed=7).generate("finance").to_dict() != \
        VaultGenerator(seed=8).generate("finance").to_dict()


def test_generator_batch_is_reproducible():
    def ids(seed):
        return [(s.attack_class.id, s.vault.canary_set.obvious[0])
                for s in ScenarioGenerator(seed=seed).generate_batch(5)]
    assert ids(3) == ids(3)


def test_bad_seed_is_a_400(client):
    pid = client.post("/api/projects", json={"name": "rt", "agent_type": "generic"}).json()["id"]
    r = client.post(f"/api/projects/{pid}/redteam", json={"preset": "privacy_core", "seed": "x"})
    assert r.status_code == 400
