"""Tests for the A2A-style AgentCard model (core/agentcard.py)."""

from __future__ import annotations

import pytest

from agentleak.core.agentcard import AgentCard, UnsafeURLError, fetch_agent_card, parse_agent_card

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


# -- fetch_agent_card SSRF guard (unit-level, no network) ------------------
# The web API tests in test_agent_api.py exercise the same guard end-to-end
# through the HTTP endpoint; these unit tests pin down the exact classification
# (UnsafeURLError vs. plain ValueError) for each rejection reason.

@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://example.com/agent-card.json",
    "javascript:alert(1)",
    "",
    "not-a-url-at-all",
])
def test_fetch_agent_card_rejects_disallowed_scheme(url: str):
    with pytest.raises(UnsafeURLError):
        fetch_agent_card(url)


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/card.json",
    "http://localhost/card.json",
    "http://169.254.169.254/latest/meta-data/",   # cloud metadata service
    "http://[::1]/card.json",                     # IPv6 loopback literal
    "http://10.0.0.5/card.json",                  # RFC1918 private
    "http://192.168.1.1/card.json",                # RFC1918 private
    "http://0.0.0.0/card.json",                    # unspecified
    "http://100.64.0.1/card.json",                 # carrier-grade NAT
])
def test_fetch_agent_card_rejects_internal_addresses(url: str):
    with pytest.raises(UnsafeURLError, match="disallowed"):
        fetch_agent_card(url)


def test_fetch_agent_card_rejects_embedded_credentials():
    with pytest.raises(UnsafeURLError, match="credential"):
        fetch_agent_card("http://user:pass@example.com/agent-card.json")


def test_fetch_agent_card_rejects_missing_host():
    with pytest.raises(UnsafeURLError, match="host"):
        fetch_agent_card("http:///agent-card.json")


def test_fetch_agent_card_allows_public_ip_literal_past_ssrf_guard(monkeypatch):
    """A public IP literal passes the SSRF guard (network still mocked here)."""
    import agentleak.core.agentcard as agentcard_mod

    def fake_open(req, timeout=None):
        raise OSError("connection refused")  # SSRF guard passed; transport fails

    monkeypatch.setattr(agentcard_mod._SAFE_OPENER, "open", fake_open)
    with pytest.raises(ValueError) as exc_info:
        fetch_agent_card("http://8.8.8.8/agent-card.json")
    assert not isinstance(exc_info.value, UnsafeURLError)


def test_fetch_agent_card_dns_failure_is_plain_value_error():
    """An unresolvable host is a network problem, not an SSRF finding."""
    with pytest.raises(ValueError) as exc_info:
        fetch_agent_card("https://this-host-does-not-exist.invalid/agent-card.json")
    assert not isinstance(exc_info.value, UnsafeURLError)


def test_fetch_agent_card_mocked_https_success(monkeypatch):
    import json as _json

    import agentleak.core.agentcard as agentcard_mod

    class _Resp:
        def __init__(self, payload: dict) -> None:
            self._b = _json.dumps(payload).encode()

        def read(self) -> bytes:
            return self._b

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        agentcard_mod._SAFE_OPENER, "open",
        lambda req, timeout=None: _Resp({"name": "remote-agent", "capabilities": ["chat"]}),
    )
    card = fetch_agent_card("https://example.com/agent-card.json")
    assert card.name == "remote-agent"


def test_fetch_agent_card_redirect_to_internal_address_is_blocked(monkeypatch):
    """A redirect landing on an internal address must be rejected, not followed."""
    import agentleak.core.agentcard as agentcard_mod

    def fake_open(req, timeout=None):
        # Simulate what HTTPRedirectHandler.redirect_request would do: the
        # opener revalidates the new URL, which here points at the metadata IP.
        agentcard_mod._assert_safe_http_url("http://169.254.169.254/agent-card.json")
        raise AssertionError("should not be reached — redirect must be rejected first")

    monkeypatch.setattr(agentcard_mod._SAFE_OPENER, "open", fake_open)
    with pytest.raises(UnsafeURLError, match="disallowed"):
        fetch_agent_card("https://example.com/agent-card.json")
