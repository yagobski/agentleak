# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""AgentLeak as a LiteLLM guardrail, exercised against the real base class."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("litellm")

from agentleak.defenses.tokenizer import TOKEN_RE  # noqa: E402
from agentleak.integrations.litellm_guardrail import AgentLeakGuardrail  # noqa: E402

SIN = "046 454 286"
POLICY = [
    {"data_type": "sin", "to": "kyc", "for": "identity_check"},
    {"data_type": "group:health", "to": "*", "deny": True},
]


def _pre(guard, text):
    data = {"model": "gpt-x", "messages": [{"role": "user", "content": text}]}
    return asyncio.run(guard.async_pre_call_hook(None, None, data, "completion"))


def test_it_is_a_litellm_custom_guardrail():
    from litellm.integrations.custom_guardrail import CustomGuardrail
    assert issubclass(AgentLeakGuardrail, CustomGuardrail)


def test_clean_request_passes():
    guard = AgentLeakGuardrail(flows=POLICY, guardrail_name="agentleak")
    assert _pre(guard, "hello")["messages"][0]["content"] == "hello"


def test_refused_value_is_redacted():
    guard = AgentLeakGuardrail(flows=POLICY, guardrail_name="agentleak")
    assert SIN not in _pre(guard, f"SIN {SIN}")["messages"][0]["content"]


def test_denied_flow_raises():
    guard = AgentLeakGuardrail(flows=POLICY, guardrail_name="agentleak")
    with pytest.raises(ValueError, match="AgentLeak"):
        _pre(guard, "the patient has diabetes")


def test_tokens_are_restored_in_the_answer():
    guard = AgentLeakGuardrail(flows=POLICY, style="token", guardrail_name="agentleak")
    sent = _pre(guard, f"look up {SIN}")["messages"][0]["content"]
    token = TOKEN_RE.search(sent).group(0)
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=f"found {token}"))])
    asyncio.run(guard.async_post_call_success_hook({}, None, response))
    assert response.choices[0].message.content == f"found {SIN}"


def test_config_comes_from_the_environment(tmp_path, monkeypatch):
    cfg = tmp_path / "agentleak.yaml"
    cfg.write_text("privacy_policy:\n  flows:\n    - data_type: email\n      to: '*'\n      deny: true\n")
    monkeypatch.setenv("AGENTLEAK_CONFIG", str(cfg))
    with pytest.raises(ValueError):
        _pre(AgentLeakGuardrail(guardrail_name="agentleak"), "mail jean@example.com")
