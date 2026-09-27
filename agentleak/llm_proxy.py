# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""An OpenAI-compatible proxy that judges what an agent sends to its model.

The MCP proxy guards the tools an agent calls. The model is the other place data
leaves: every prompt is a message to a third party, and a tool result pasted
into the next turn carries whatever the tool returned. Gateways such as
LiteLLM, Portkey and Lasso sit on this path; AgentLeak had nothing there.

Point an OpenAI-style client at it instead of the provider:

    agentleak llm-proxy --upstream https://api.openai.com --config agentleak.yaml
    OPENAI_BASE_URL=http://127.0.0.1:8788/v1  your-agent

Each request's ``messages`` (chat), ``input`` (responses, embeddings) or
``prompt`` (legacy completions) is judged by the same
:class:`~agentleak.defenses.gateway.Gateway` and flow rules the MCP proxy uses,
with the provider as recipient. Permitted content is forwarded unchanged,
refused values are redacted (or tokenized), and a flow a ``deny`` rule names is
refused with an OpenAI-shaped error the client already knows how to surface.
Every decision goes to the same hash-chained, optionally signed evidence log.

Limits, stated rather than hidden: a streamed response (``"stream": true``) is
passed through unjudged and tokens in it are not restored — the request is
still judged. Only JSON POST bodies are inspected; other routes are forwarded
as they are. It binds to loopback by default, because it holds the upstream
credentials' traffic.
"""

from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .defenses.gateway import Action, Gateway

__all__ = ["LlmProxy", "judged_fields", "run_llm_proxy"]

# The request fields that carry content to the model, per API shape.
_CONTENT_FIELDS = ("messages", "input", "prompt", "system", "instructions")
# Hop-by-hop headers are not forwarded (RFC 9110 §7.6.1), nor is the length,
# which changes when content is redacted.
_DROP_HEADERS = {"host", "connection", "keep-alive", "transfer-encoding", "content-length",
                 "proxy-authorization", "te", "trailer", "upgrade", "accept-encoding"}


def judged_fields(body: dict[str, Any]) -> dict[str, Any]:
    return {key: body[key] for key in _CONTENT_FIELDS if key in body}


def _provider_name(upstream: str) -> str:
    host = urllib.parse.urlparse(upstream).hostname or "llm"
    parts = host.split(".")
    # api.openai.com -> openai; openrouter.ai -> openrouter; localhost -> localhost
    return parts[-2] if len(parts) >= 2 else parts[0]


def _refusal(decision: Any) -> dict[str, Any]:
    return {"error": {
        "message": (
            f"Blocked by AgentLeak privacy policy: {decision.reason}. "
            "This request was not sent to the model."
        ),
        "type": "agentleak_policy_violation",
        "code": "privacy_policy",
        "agentleak": decision.to_dict(),
    }}


class LlmProxy:
    """Judges model requests (and optionally responses) before they pass."""

    def __init__(
        self,
        upstream: str,
        *,
        gateway: Gateway,
        recipient: str = "",
        agent: str = "llm-client",
        inspect_responses: bool = False,
        verbose: bool = False,
        timeout: float = 600.0,
    ) -> None:
        self.upstream = upstream.rstrip("/")
        self.gateway = gateway
        self.recipient = recipient or _provider_name(upstream)
        self.agent = agent
        self.inspect_responses = inspect_responses
        self.verbose = verbose
        self.timeout = timeout
        self.counts = {"allow": 0, "redact": 0, "block": 0}
        self._lock = threading.Lock()

    def _note(self, message: str) -> None:
        if self.verbose:
            print(f"[agentleak] {message}", file=sys.stderr, flush=True)

    def _count(self, action: str) -> None:
        with self._lock:
            self.counts[action] = self.counts.get(action, 0) + 1

    # ------------------------------------------------------------------
    def judge_request(self, body: dict[str, Any], path: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Return ``(body to forward, refusal)``; exactly one is not None."""
        content = judged_fields(body)
        if not content:
            return body, None
        purpose = str((body.get("metadata") or {}).get("purpose") or "") if isinstance(
            body.get("metadata"), dict) else ""
        decision = self.gateway.check(
            content,
            tool=f"{self.recipient}/{body.get('model', path)}",
            recipient=self.recipient,
            sender=self.agent,
            purpose=purpose,
        )
        self._count(decision.action)
        if decision.action == Action.BLOCK:
            self._note(f"BLOCK {path}: {decision.reason}")
            return None, _refusal(decision)
        if decision.action == Action.REDACT:
            self._note(f"REDACT {path}: {decision.reason}")
            return {**body, **decision.arguments}, None
        return body, None

    def judge_response(self, payload: dict[str, Any], model: str) -> dict[str, Any]:
        """Judge a non-streamed response on its way back, then restore tokens."""
        if self.inspect_responses:
            decision = self.gateway.check(
                payload.get("choices") or payload.get("output") or payload,
                tool=f"{self.recipient}/{model}",
                recipient=self.agent,
                sender=self.recipient,
                direction="response",
            )
            if decision.action == Action.BLOCK:
                self._count("block")
                return _refusal(decision)
            if decision.action == Action.REDACT:
                self._count("redact")
                key = "choices" if "choices" in payload else "output" if "output" in payload else None
                payload = {**payload, key: decision.arguments} if key else decision.arguments
        tokenizer = self.gateway.sanitizer.tokenizer
        if tokenizer is not None and len(tokenizer) > 0:
            restored = tokenizer.restore_obj(payload)
            if isinstance(restored, dict):
                payload = restored
        return payload

    # ------------------------------------------------------------------
    def handler(self) -> type[BaseHTTPRequestHandler]:
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                return  # decisions are narrated by the proxy, not the access log

            def _send_json(self, status: int, payload: dict[str, Any]) -> None:
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _forward(self, method: str) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                body: dict[str, Any] | None = None
                if raw and "json" in (self.headers.get("Content-Type") or "json"):
                    try:
                        parsed = json.loads(raw)
                        body = parsed if isinstance(parsed, dict) else None
                    except json.JSONDecodeError:
                        body = None
                streaming = bool(body and body.get("stream"))
                if body is not None and method == "POST":
                    forward, refusal = proxy.judge_request(body, self.path)
                    if refusal is not None:
                        self._send_json(403, refusal)
                        return
                    raw = json.dumps(forward).encode()

                headers = {k: v for k, v in self.headers.items() if k.lower() not in _DROP_HEADERS}
                request = urllib.request.Request(
                    proxy.upstream + self.path, data=raw if method == "POST" else None,
                    headers=headers, method=method,
                )
                try:
                    response = urllib.request.urlopen(request, timeout=proxy.timeout)  # noqa: S310 - the user's upstream
                    status, resp_headers = response.status, response.headers
                except urllib.error.HTTPError as err:
                    response, status, resp_headers = err, err.code, err.headers

                with response:
                    if streaming or "json" not in (resp_headers.get("Content-Type") or ""):
                        # Streamed or non-JSON: relay as it arrives, untouched.
                        self.send_response(status)
                        for key, value in resp_headers.items():
                            if key.lower() not in _DROP_HEADERS:
                                self.send_header(key, value)
                        self.send_header("Connection", "close")
                        self.end_headers()
                        while chunk := response.read(8192):
                            self.wfile.write(chunk)
                            self.wfile.flush()
                        self.close_connection = True
                        return
                    payload_raw = response.read()
                try:
                    payload = json.loads(payload_raw)
                except json.JSONDecodeError:
                    payload = None
                if isinstance(payload, dict) and status < 400:
                    payload = proxy.judge_response(payload, str((body or {}).get("model", "")))
                    self._send_json(status, payload)
                    return
                self.send_response(status)
                self.send_header("Content-Type", resp_headers.get("Content-Type") or "application/json")
                self.send_header("Content-Length", str(len(payload_raw)))
                self.end_headers()
                self.wfile.write(payload_raw)

            def do_POST(self) -> None:  # noqa: N802
                self._forward("POST")

            def do_GET(self) -> None:  # noqa: N802
                self._forward("GET")

        return Handler

    def serve(self, host: str = "127.0.0.1", port: int = 8788) -> ThreadingHTTPServer:
        server = ThreadingHTTPServer((host, port), self.handler())
        return server


def run_llm_proxy(
    upstream: str,
    *,
    flows: Any = None,
    groups: dict[str, Any] | None = None,
    evidence: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8788,
    recipient: str = "",
    agent: str = "llm-client",
    block_on_violation: bool = False,
    inspect_responses: bool = False,
    style: str = "placeholder",
    sign_key: str | None = None,
    verbose: bool = True,
) -> int:
    gateway = Gateway(
        flows=flows, groups=groups, evidence=evidence, block_on_violation=block_on_violation,
        agent=agent, redaction_style=style, sign_key=sign_key,
    )
    proxy = LlmProxy(upstream, gateway=gateway, recipient=recipient, agent=agent,
                     inspect_responses=inspect_responses, verbose=verbose)
    server = proxy.serve(host, port)
    proxy._note(f"judging model traffic to {proxy.upstream} as recipient '{proxy.recipient}' "
                f"on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover
        pass
    finally:
        server.server_close()
        proxy._note(f"stopped — {proxy.counts}")
    return 0
