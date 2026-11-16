# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""A configuration file cannot send an arbitrary environment variable anywhere.

In CI the configuration is often a file a pull request can edit. Before this
rule, ``detection.llm_judge.api_key_env: GITHUB_TOKEN`` with a ``base_url`` of
the pull request's choosing made AgentLeak send that token to that host.
"""

from __future__ import annotations

import http.server
import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from agentleak.core.keys import ALLOW_ENV, default_key, key_for, refusal

SECRET = "synthetic-" + "q" * 20


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (ALLOW_ENV, "OPENAI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY",
                 "GROQ_API_KEY", "TOGETHER_API_KEY", "AGENTLEAK_LLM_URL"):
        monkeypatch.delenv(name, raising=False)


# ---------------------------------------------------------------- the rule

@pytest.mark.parametrize("name,url", [
    ("OPENAI_API_KEY", "https://api.openai.com/v1"),
    ("OPENAI_API_KEY", "https://eu.api.openai.com/v1"),
    ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1"),
    ("ANTHROPIC_API_KEY", "https://api.anthropic.com/v1"),
    ("MY_LOCAL_API_KEY", "http://localhost:11434/v1"),
    ("OPENAI_API_KEY", "http://127.0.0.1:8080/v1"),
    ("VLLM_API_KEY", "http://[::1]:8000/v1"),
])
def test_allowed_pairs(name: str, url: str) -> None:
    assert refusal(name, url) is None


@pytest.mark.parametrize("name,url", [
    ("GITHUB_TOKEN", "https://attacker.example/v1"),
    ("GITHUB_TOKEN", "http://127.0.0.1:9/v1"),          # not *_API_KEY, even locally
    ("AL_GITHUB_TOKEN", "https://api.openai.com/v1"),
    ("OPENAI_API_KEY", "https://attacker.example/v1"),
    ("OPENAI_API_KEY", "https://api.openai.com.attacker.example/v1"),
    ("OPENAI_API_KEY", "https://evilapi.openai.com/v1"),
    ("OPENAI_API_KEY", "https://openrouter.ai/api/v1"),  # right shape, wrong provider
    ("MY_LOCAL_API_KEY", "https://attacker.example/v1"),
    ("AWS_SECRET_ACCESS_KEY", "https://api.openai.com/v1"),
    ("lower_api_key", "http://localhost/v1"),
    ("", "https://api.openai.com/v1"),
    ("PATH; rm", "https://api.openai.com/v1"),
])
def test_refused_pairs(name: str, url: str) -> None:
    if name == "":
        assert key_for(name, url) == ("", None)
    else:
        assert refusal(name, url)


def test_refused_value_is_never_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", SECRET)
    value, why = key_for("GITHUB_TOKEN", "https://attacker.example/v1")
    assert value == ""
    assert why and f"{ALLOW_ENV}=GITHUB_TOKEN@attacker.example" in why


def test_operator_can_allow_a_name_for_a_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_KEY", SECRET)
    monkeypatch.setenv(ALLOW_ENV, " AZURE_KEY@example-openai.azure.com , OTHER ")
    assert key_for("AZURE_KEY", "https://example-openai.azure.com/openai") == (SECRET, None)
    assert key_for("AZURE_KEY", "https://res.example-openai.azure.com/x")[0] == SECRET
    assert key_for("AZURE_KEY", "https://attacker.example/")[0] == ""


def test_operator_can_allow_a_name_for_any_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COMPANY_LLM_KEY", SECRET)
    monkeypatch.setenv(ALLOW_ENV, "COMPANY_LLM_KEY")
    assert key_for("COMPANY_LLM_KEY", "https://llm.company.example/v1") == (SECRET, None)


def test_default_key_gives_unknown_hosts_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    assert default_key("https://api.openai.com/v1") == SECRET
    assert default_key("https://attacker.example/v1") == ""


# ------------------------------------------------------------ the call sites

def test_live_agent_key_resolution_no_longer_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    from agentleak.agent.llm import resolve_api_key

    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET + "r")
    assert resolve_api_key("https://api.openai.com/v1") == SECRET
    assert resolve_api_key("https://openrouter.ai/api/v1") == SECRET + "r"
    assert resolve_api_key("https://attacker.example/v1") == ""
    assert resolve_api_key("https://attacker.example/v1", "explicit") == "explicit"


def test_judge_default_key_follows_the_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    from agentleak.detectors.llm_judge import LLMJudgeDetector

    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    assert LLMJudgeDetector(base_url="https://attacker.example/v1")._api_key == ""
    assert LLMJudgeDetector(base_url="https://api.openai.com/v1")._api_key == SECRET


def test_bench_manifest_cannot_send_any_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    from agentleak.research import bench
    from agentleak.research.manifest import AgentSettings

    monkeypatch.setenv("GITHUB_TOKEN", SECRET)

    class _Manifest:
        agent = AgentSettings(mode="live", base_url="https://attacker.example/v1",
                              model="m", api_key_env="GITHUB_TOKEN")

    with pytest.raises(bench.RunError, match="GITHUB_TOKEN"):
        bench._live_llm(_Manifest())  # type: ignore[arg-type]


class _Listener:
    def __init__(self) -> None:
        self.auth: list[str] = []
        seen = self.auth

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - http.server API
                self.rfile.read(int(self.headers.get("content-length", 0)))
                seen.append(self.headers.get("Authorization", ""))
                body = json.dumps({"choices": [{"message": {"content": "[]"}}]}).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args: object) -> None:
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def listener() -> Iterator[_Listener]:
    srv = _Listener()
    yield srv
    srv.server.shutdown()


def _run_with_judge(tmp_path: Path, url: str, key_env: str) -> list[str]:
    from agentleak.core.config import Config
    from agentleak.core.runner import AgentLeakRunner
    from agentleak.core.trace import Trace
    from agentleak.scenarios import load_example_trace

    cfg_path = tmp_path / "agentleak.yaml"
    cfg_path.write_text(
        "detection:\n"
        "  mode: hybrid\n"
        "  llm_judge:\n"
        "    enabled: true\n"
        f"    base_url: {url}\n"
        "    model: m\n"
        f"    api_key_env: {key_env}\n"
    )
    trace = load_example_trace("healthcare_patient_summary")
    assert isinstance(trace, Trace)
    result = AgentLeakRunner(config=Config.load(str(cfg_path))).analyze(trace)
    return list(result.warnings)


def test_pull_request_config_cannot_exfiltrate_a_token(
    tmp_path: Path, listener: _Listener, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", SECRET)
    warnings = _run_with_judge(tmp_path, listener.url, "GITHUB_TOKEN")
    assert not any(SECRET in auth for auth in listener.auth)
    assert any("was not sent" in w for w in warnings)


def test_operator_allowed_local_key_still_reaches_the_judge(
    tmp_path: Path, listener: _Listener, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LOCAL_JUDGE_API_KEY", SECRET)
    _run_with_judge(tmp_path, listener.url, "LOCAL_JUDGE_API_KEY")
    assert listener.auth and all(SECRET in auth for auth in listener.auth)
