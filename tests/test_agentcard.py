"""Tests for the A2A-style AgentCard model (core/agentcard.py)."""

from __future__ import annotations

import pytest

from agentleak.core.agentcard import AgentCard, parse_agent_card


NASIKO_CARD = {
    "name": "document-analyzer",
    "description": "AI agent for document analysis and extraction",
    "capabilities": ["document_analysis", "pdf_extraction", "text_summarization"],
    "tags": ["nlp", "documents", "analysis"],
    "examples": ["analyze this contract", "extract data from PDF"],
    "input_mode": "text",
    "output_mode": "json",
    "agent_protocol_version": "a2a-v1",
    "endpoints": {"/analyze": "Analyze document content", "/health": "Health check"},
}


def test_parse_nasiko_card_roundtrip():
    card = parse_agent_card(NASIKO_CARD)
    assert card.name == "document-analyzer"
    assert card.capabilities == NASIKO_CARD["capabilities"]
    assert card.endpoints["/health"] == "Health check"
    assert card.agent_protocol_version == "a2a-v1"
    assert card.is_valid
    data = card.to_dict()
    assert data["name"] == NASIKO_CARD["name"]
    assert data["output_mode"] == "json"
    # Roundtrip is stable.
    assert AgentCard.from_dict(data).to_dict() == data


def test_parse_official_a2a_card_variants():
    card = parse_agent_card({
        "name": "github-agent",
        "protocolVersion": "0.2.5",
        "provider": {"organization": "Acme"},
        "capabilities": {"streaming": True, "pushNotifications": False},
        "skills": [{"id": "repo_query", "name": "Repo query"}, "commit_summary"],
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["json"],
    })
    assert card.agent_protocol_version == "0.2.5"
    assert card.provider == "Acme"
    assert "streaming" in card.capabilities
    assert "pushNotifications" not in card.capabilities
    assert "repo_query" in card.capabilities
    assert "commit_summary" in card.capabilities
    assert card.input_mode == "text"
    assert card.output_mode == "json"


def test_validation_errors():
    assert "'name' is required." in AgentCard(name="").validate()
    assert AgentCard(name="x").validate()  # missing capabilities
    # Modes and protocol versions are free-form — the ecosystem moves faster
    # than any whitelist. Only structural coherence is enforced.
    assert AgentCard(
        name="x", capabilities=["a"], input_mode="video",
        output_mode="protobuf", agent_protocol_version="acp-v3",
    ).validate() == []
    assert any("input_mode" in e for e in AgentCard(name="x", capabilities=["a"], input_mode="  ").validate())
    card = AgentCard(name="x", capabilities=["a"], source={"type": "github"})
    assert any("source.repo" in e for e in card.validate())
    card = AgentCard(name="x", capabilities=["a"], source={"type": "carrier-pigeon"})
    assert any("source.type" in e for e in card.validate())


def test_valid_card_with_source_and_privacy():
    card = AgentCard(
        name="support-bot",
        capabilities=["ticket_triage"],
        source={"type": "github", "repo": "acme/support-bot", "branch": "main"},
        privacy={"declared_data_types": ["email", "phone_number"]},
    )
    assert card.validate() == []
    data = card.to_dict()
    assert data["source"]["repo"] == "acme/support-bot"
    assert data["privacy"]["declared_data_types"] == ["email", "phone_number"]


def test_parse_from_json_string_and_bad_json():
    card = parse_agent_card('{"name": "x", "capabilities": ["a"]}')
    assert card.name == "x"
    with pytest.raises(ValueError):
        parse_agent_card("{not json")
    with pytest.raises(ValueError):
        parse_agent_card([1, 2, 3])  # type: ignore[arg-type]
