# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Encoded and obscured copies passed between agents.

Before this existed, ten such copies sent from a planner to its workers were
analysed and one was found — a reversed SIN that still looked like a SIN, and
was then counted as a *different* SIN. Every case below was missed.
"""

from __future__ import annotations

import base64
import codecs
import hashlib
import json
import os
import urllib.parse
import uuid

import pytest

from agentleak.core.runner import analyze
from agentleak.core.trace import Trace
from agentleak.core.transforms import decoded_views
from agentleak.defenses import sanitize_text
from agentleak.defenses.gateway import Action, Gateway

RECORD = {
    "name": "Jean Tremblay",
    "sin": "046 454 286",
    "email": "jean.tremblay@example.com",
    "diagnosis": "Type 2 diabetes",
    "api_key": "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789",
}
SIN = RECORD["sin"]
EMAIL = RECORD["email"]


def _b64(value: str) -> str:
    return base64.b64encode(value.encode()).decode()


def _trace(*messages: tuple[str, str]) -> Trace:
    events = [
        {"event_id": "e1", "channel": "tool_response", "source": "crm",
         "target": "planner", "content": RECORD},
    ]
    for i, (target, content) in enumerate(messages, start=2):
        events.append({"event_id": f"e{i}", "channel": "inter_agent_message",
                       "source": "planner", "target": target, "content": content})
    return Trace.model_validate({"run_id": "enc", "agent_name": "planner", "events": events})


def _disclosed(trace: Trace) -> dict[str, set[tuple[str, str]]]:
    """event_id -> {(data_type, transform)} on the inter-agent channel."""
    out: dict[str, set[tuple[str, str]]] = {}
    for f in analyze(trace).findings:
        if f.channel == "inter_agent_message":
            out.setdefault(f.event_id, set()).add((f.data_type, f.metadata.get("transform", "")))
    return out


@pytest.mark.parametrize(
    "content, data_type, transform",
    [
        ("ctx=" + _b64(json.dumps(RECORD)), "sin", "base64"),
        ("ctx=" + _b64(json.dumps(RECORD)), "llm_api_key", "base64"),
        ("ref " + _b64(SIN), "sin", "base64"),
        ("id=" + EMAIL.encode().hex(), "email", "hex"),
        ("https://t.example/p?u=" + urllib.parse.quote(EMAIL, safe=""), "email", "percent"),
        ("contact " + " ".join(EMAIL), "email", "spaced"),
        ("cfg " + _b64(_b64(SIN)), "sin", "base64>base64"),
        ("note: " + codecs.encode("Type 2 diabetes", "rot13"), "health_condition", "rot13"),
        ("code " + SIN[::-1], "sin", "reversed"),
    ],
)
def test_encoded_copy_between_agents_is_found(content, data_type, transform):
    found = _disclosed(_trace(("worker", content)))
    assert (data_type, transform) in found.get("e2", set()), found


def test_value_split_across_messages_to_one_recipient():
    found = _disclosed(_trace(("worker", "part one: 046 454"), ("worker", "part two: 286")))
    assert ("sin", "split") in found.get("e3", set()), found


def test_split_needs_one_recipient():
    # Two different recipients each hold half; neither can read the SIN.
    found = _disclosed(_trace(("worker_a", "part one: 046 454"), ("worker_b", "part two: 286")))
    assert not any(t == "split" for s in found.values() for _, t in s)


def test_split_fragments_are_whole_tokens():
    # "046454" buried inside a longer number is not a fragment of the SIN.
    trace = _trace(("w", "ref 2046454"), ("w", "then 286"))
    assert not any(t == "split" for s in _disclosed(trace).values() for _, t in s)


def test_split_is_for_identifiers_not_phrases():
    # Found in the AgentDojo pack: a placeholder "{hotel_address" reassembled
    # from one message saying "Hotel" and another saying "address".
    events = [
        {"event_id": "e1", "channel": "tool_response", "source": "crm", "target": "a",
         "content": {"address": "{hotel_address"}},
        {"event_id": "e2", "channel": "tool_response", "source": "t", "target": "a",
         "content": "Hotel Names: Le Marais"},
        {"event_id": "e3", "channel": "tool_response", "source": "t", "target": "a",
         "content": "the address is on file"},
    ]
    trace = Trace.model_validate({"run_id": "p", "agent_name": "a", "events": events})
    assert not any(f.metadata.get("transform") == "split" for f in analyze(trace).findings)


def test_encoded_copy_is_the_same_secret_not_a_new_one():
    plain = analyze(_trace(("worker", "ok"))).score.agentrisk
    encoded = analyze(_trace(("worker", "ref " + _b64(SIN)), ("w2", "code " + SIN[::-1]))).score.agentrisk
    # Same vault: the copies are the SIN already in the tool response.
    assert encoded.vault_count == plain.vault_count
    assert encoded.rho_s == plain.rho_s
    assert encoded.leaked_count > plain.leaked_count


def test_reversed_sin_is_not_counted_as_a_second_sin():
    findings = analyze(_trace(("worker", "code " + SIN[::-1]))).findings
    values = {f.matched_value for f in findings if f.data_type == "sin"}
    assert values == {SIN}


def test_plaintext_digits_are_not_called_rot13():
    # ROT13 leaves digits alone; a plaintext number the detectors missed is
    # not an obscured copy of itself.
    trace = _trace(("worker", "income noted as 046 454 286 in the file"))
    for f in analyze(trace).findings:
        assert f.metadata.get("transform") != "rot13"


BENIGN = [
    "sha256 " + hashlib.sha256(b"x").hexdigest(),
    "commit 3f9c2a7e1b4d8c6f0a2e5b7d9c1f3a5e7b9d1c3f merged",
    "request " + str(uuid.uuid4()) + " " + uuid.uuid4().hex,
    "data:image/png;base64," + base64.b64encode(bytes([137, 80, 78, 71]) + os.urandom(300)).decode(),
    "https://www.google.com/search?q=privacy%20for%20ai%20agents&hl=en",
    "color: #ff00aa; border: #123456",
    "config=" + _b64("retries=3 timeout=30 region=ca-central-1"),
    "ciphertext " + base64.b64encode(os.urandom(48)).decode(),
    "SuperCalifragilisticExpialidocious is a long word",
    "letters a b c d e f g h i j in a list",
]


@pytest.mark.parametrize("text", BENIGN)
def test_benign_encoded_looking_text_is_left_alone(text):
    assert sanitize_text(text) == text
    events = [{"event_id": "e1", "channel": "log", "source": "a", "target": "b", "content": text}]
    trace = Trace.model_validate({"run_id": "b", "agent_name": "a", "events": events})
    assert analyze(trace).findings == []


def test_binary_decodes_are_dropped():
    assert decoded_views(base64.b64encode(os.urandom(64)).decode()) == []


def test_redact_removes_the_encoded_token_whole_labelled_by_the_worst_inside():
    assert sanitize_text("ctx=" + _b64(json.dumps(RECORD))) == "ctx=[REDACTED_LLM_API_KEY]"
    assert sanitize_text("ref " + _b64(SIN)) == "ref [REDACTED_SIN]"


def test_redact_cuts_only_the_encoded_url_segment():
    text = "GET /users/" + urllib.parse.quote(EMAIL, safe="") + "/orders?page=2"
    assert sanitize_text(text) == "GET /users/[REDACTED_EMAIL]/orders?page=2"


def test_encoded_password_inside_a_dsn_is_the_dsn_not_an_email():
    text = "postgresql://billing:S3cr3tP%40ssw0rd@db.internal:5432/payments"
    assert sanitize_text(text) == "[REDACTED_CONNECTION_STRING]"
    events = [{"event_id": "e1", "channel": "log", "source": "a", "target": "b", "content": text}]
    trace = Trace.model_validate({"run_id": "d", "agent_name": "a", "events": events})
    assert {f.data_type for f in analyze(trace).findings} == {"connection_string"}


def test_gateway_redacts_an_encoded_value_surgically():
    gateway = Gateway(flows=[{"data_type": "sin", "to": "kyc", "for": "identity_check"}])
    decision = gateway.check({"ref": _b64(SIN), "order": "ORD-7781"}, recipient="analytics")
    assert decision.action == Action.REDACT
    assert decision.arguments == {"ref": "[REDACTED_SIN]", "order": "ORD-7781"}
