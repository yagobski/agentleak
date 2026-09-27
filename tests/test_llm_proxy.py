# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The model is the other place data leaves: judge what is sent to it.

Every test runs a real HTTP round trip: client -> LlmProxy -> a stub upstream
that records what it received and answers like an OpenAI-compatible API.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from agentleak.defenses.gateway import Gateway
from agentleak.defenses.tokenizer import TOKEN_RE
from agentleak.llm_proxy import LlmProxy

SIN = "046 454 286"
POLICY = [
    {"data_type": "sin", "to": "kyc", "for": "identity_check"},
    {"data_type": "group:health", "to": "*", "deny": True},
]


class _Upstream:
    def __init__(self, answer: str = "") -> None:
        self.received: list[dict] = []
        self.headers: list[dict] = []
        self.answer = answer
        upstream = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):  # noqa: D401
                return

            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                upstream.received.append(body)
                upstream.headers.append(dict(self.headers))
                if body.get("stream"):
                    data = b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n'
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                text = upstream.answer or "echo: " + json.dumps(body.get("messages"))
                out = json.dumps({"id": "c1", "object": "chat.completion", "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": text}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out)))
                self.end_headers()
                self.wfile.write(out)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"


@pytest.fixture
def stack(tmp_path):
    made = []

    def build(answer: str = "", **kwargs):
        upstream = _Upstream(answer)
        style = kwargs.pop("style", "placeholder")
        gateway = Gateway(flows=POLICY, evidence=str(tmp_path / "e.jsonl"),
                          agent="app", redaction_style=style)
        proxy = LlmProxy(upstream.url, gateway=gateway, recipient="openai", agent="app", **kwargs)
        server = proxy.serve("127.0.0.1", 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        made.extend([upstream.server, server])
        return upstream, f"http://127.0.0.1:{server.server_address[1]}"

    yield build
    for server in made:
        server.shutdown()


def _post(base: str, body: dict, headers: dict | None = None):
    req = urllib.request.Request(base + "/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def _chat(text: str, **extra) -> dict:
    return {"model": "gpt-x", "messages": [{"role": "user", "content": text}], **extra}


def test_clean_request_passes_unchanged(stack):
    upstream, base = stack()
    status, body, _ = _post(base, _chat("Summarise the release notes."))
    assert status == 200
    assert upstream.received[0]["messages"][0]["content"] == "Summarise the release notes."
    assert json.loads(body)["choices"][0]["message"]["content"].startswith("echo:")


def test_refused_value_is_redacted_before_the_model_sees_it(stack):
    upstream, base = stack()
    status, _, _ = _post(base, _chat(f"Customer SIN is {SIN}, draft a reply."))
    assert status == 200
    sent = upstream.received[0]["messages"][0]["content"]
    assert SIN not in sent and "draft a reply" in sent


def test_denied_flow_never_reaches_the_model(stack):
    upstream, base = stack()
    status, body, _ = _post(base, _chat("The patient was diagnosed with diabetes."))
    assert status == 403 and upstream.received == []
    error = json.loads(body)["error"]
    assert error["type"] == "agentleak_policy_violation"


def test_credentials_headers_are_forwarded(stack):
    upstream, base = stack()
    _post(base, _chat("hello"), {"Authorization": "Bearer sk-test"})
    assert upstream.headers[0]["Authorization"] == "Bearer sk-test"


def test_tokens_reach_the_model_and_come_back_as_values(stack):
    upstream, base = stack(style="token")
    status, body, _ = _post(base, _chat(f"Look up {SIN} and confirm it."))
    sent = upstream.received[0]["messages"][0]["content"]
    assert SIN not in sent and TOKEN_RE.search(sent)
    assert SIN in json.loads(body)["choices"][0]["message"]["content"]


def test_inspected_response_is_redacted(stack):
    upstream, base = stack(answer=f"The SIN on file is {SIN}.", inspect_responses=True)
    status, body, _ = _post(base, _chat("What is on file?"))
    assert status == 200 and SIN not in json.loads(body)["choices"][0]["message"]["content"]


def test_a_stream_is_relayed_and_its_request_still_judged(stack):
    upstream, base = stack()
    status, body, headers = _post(base, _chat(f"SIN {SIN}", stream=True))
    assert status == 200 and b"[DONE]" in body
    assert "event-stream" in headers.get("Content-Type", "")
    assert SIN not in upstream.received[0]["messages"][0]["content"]


def test_decisions_land_in_the_evidence_log(stack, tmp_path):
    _upstream, base = stack()
    _post(base, _chat(f"SIN {SIN}"))
    entries = [json.loads(x) for x in (tmp_path / "e.jsonl").read_text().splitlines()]
    assert entries[-1]["action"] == "redact" and entries[-1]["recipient"] == "openai"
    assert SIN not in (tmp_path / "e.jsonl").read_text()
