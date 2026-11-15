# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Hosted deployments must not call model endpoints on private addresses.

docs/reports/QA-REPORT.md listed this as open: a project's ``agent.base_url``, the account
model key and the red-team override are fetched by the server. In public mode
the URL now has to resolve to a public address; self-hosted and CLI use, where
the model is usually on localhost, is unchanged.
"""
from __future__ import annotations

import urllib.request

import pytest

from agentleak.agent.llm import LLMConfig, LLMError, OpenAICompatLLM
from agentleak.core import netguard
from agentleak.core.netguard import UnsafeURLError, open_model_url, set_outbound_guard

INTERNAL = [
    "http://127.0.0.1:11434/v1/chat/completions",
    "http://localhost:8000/v1/chat/completions",
    "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.5/v1/chat/completions",
    "http://192.168.1.10:8080/v1",
    "http://[::1]:8000/v1",
    "http://0.0.0.0:8000/v1",
    "http://2130706433/v1",  # 127.0.0.1 as a decimal integer
    "http://user:secret@example.com/v1",
    "file:///etc/passwd",
]


@pytest.fixture
def no_network(monkeypatch):
    """Fail loudly if anything tries to open a connection."""
    opened: list[str] = []

    def _refuse(request, *args, **kwargs):
        opened.append(getattr(request, "full_url", str(request)))
        raise AssertionError("a request was opened")

    monkeypatch.setattr(urllib.request, "urlopen", _refuse)
    monkeypatch.setattr(netguard._SAFE_OPENER, "open", _refuse)
    return opened


def test_guard_is_off_by_default() -> None:
    assert netguard.guard_enabled() is False


def test_guard_off_reaches_localhost(monkeypatch) -> None:
    """Self-hosted and CLI use: a local model endpoint must stay reachable."""
    seen: list[str] = []

    def _fake(request, timeout):
        seen.append(request.full_url)
        return "response"

    monkeypatch.setattr(urllib.request, "urlopen", _fake)
    req = urllib.request.Request("http://127.0.0.1:11434/v1/chat/completions")
    assert open_model_url(req, timeout=1) == "response"
    assert seen == ["http://127.0.0.1:11434/v1/chat/completions"]


@pytest.mark.parametrize("url", INTERNAL)
def test_guard_on_refuses_internal_targets(url: str, no_network) -> None:
    set_outbound_guard(True)
    with pytest.raises((UnsafeURLError, ValueError)):
        open_model_url(urllib.request.Request(url), timeout=1)
    assert no_network == []


def test_llm_client_reports_a_refused_endpoint_as_llm_error(no_network) -> None:
    set_outbound_guard(True)
    client = OpenAICompatLLM(LLMConfig(base_url="http://169.254.169.254/v1", model="m", api_key="k"))
    with pytest.raises(LLMError, match="public addresses"):
        client.chat([{"role": "user", "content": "hi"}], [])
    assert no_network == []


def test_public_mode_app_turns_the_guard_on(monkeypatch, tmp_path) -> None:
    from agentleak.core.store import Store
    from agentleak.web.app import create_app

    monkeypatch.delenv("AGENTLEAK_LOCAL_MODE", raising=False)
    monkeypatch.setenv("AGENTLEAK_PUBLIC_MODE", "1")
    create_app(store=Store(str(tmp_path / "public.db")))
    assert netguard.guard_enabled() is True


def test_self_hosted_app_leaves_the_guard_off(monkeypatch, tmp_path) -> None:
    from agentleak.core.store import Store
    from agentleak.web.app import create_app

    set_outbound_guard(True)
    monkeypatch.delenv("AGENTLEAK_PUBLIC_MODE", raising=False)
    create_app(store=Store(str(tmp_path / "selfhosted.db")))
    assert netguard.guard_enabled() is False
