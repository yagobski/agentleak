# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Discovery only works if the document sits where the caller looks.

An agent finding AgentLeak does not read the docs first — it probes the
conventional locations. Two ways that fails quietly: the card is served under
one spelling while the client tries another, and a missing machine path answers
with an HTML page instead of a 404, so the client has no error to react to.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from agentleak import __version__
from agentleak.web.app import create_app

client = TestClient(create_app())

# A2A's current name, its former name, and the plugin-style convention.
CARD_PATHS = ["/.well-known/agent-card.json", "/.well-known/agent.json", "/agent.json"]


def test_the_card_is_served_at_every_name_an_agent_might_try() -> None:
    for path in CARD_PATHS:
        response = client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"
        assert response.headers["content-type"].startswith("application/json"), path


def test_every_spelling_returns_the_same_card() -> None:
    """Two names for one document must not become two documents."""
    cards = [client.get(path).json() for path in CARD_PATHS]
    assert all(json.dumps(c, sort_keys=True) == json.dumps(cards[0], sort_keys=True)
               for c in cards)


def test_the_card_says_what_it_is_and_which_version() -> None:
    card = client.get(CARD_PATHS[0]).json()
    assert card["name"]
    assert card["version"] == __version__
    assert card.get("skills"), "a card with no skills tells an agent nothing"


def test_the_text_surfaces_an_llm_reads_are_served_as_text() -> None:
    for path in ("/llms.txt", "/llms-full.txt", "/agents.md"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.text.strip(), f"{path} is empty"
