# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The proxy sits on the critical path of somebody's agent.

MCP is where agents reach the outside world, and where this year's incidents
happened: tool poisoning, name collisions sending data to the wrong tool,
confused parameter mapping posting a record to the wrong endpoint. Every one is
the same sentence — sensitive data went to the wrong recipient through a tool
call — which is the sentence this project exists for.

Two properties matter more than any feature, and both are about not breaking the
session it is inserted into: anything the proxy does not understand crosses
untouched, and a refusal arrives as something the agent can read rather than as
a broken transport.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

from agentleak.defenses.gateway import Gateway
from agentleak.mcp_proxy import McpProxy, _server_name

POLICY = [
    {"data_type": "sin", "to": "server", "for": "identity_check"},
    {"data_type": "health_condition", "to": "*", "deny": True},
]


@pytest.fixture
def proxy(tmp_path):
    gateway = Gateway(flows=POLICY, evidence=str(tmp_path / "e.jsonl"), agent="client")
    return McpProxy(["echo"], gateway=gateway, recipient="server")


def _call(tool: str, arguments: dict, purpose: str = "", request_id: int = 1) -> dict:
    message: dict = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": tool, "arguments": arguments},
    }
    if purpose:
        message["params"]["_meta"] = {"purpose": purpose}
    return message


# ----------------------------------------------------------------------
# Do not break the session
# ----------------------------------------------------------------------
@pytest.mark.parametrize("method", ["initialize", "tools/list", "resources/read", "ping"])
def test_everything_that_is_not_a_tool_call_crosses_untouched(proxy, method) -> None:
    """A proxy that half-implements MCP breaks sessions in ways nobody can
    debug. Only `tools/call` is interpreted; the rest is forwarded verbatim.
    """
    message = {"jsonrpc": "2.0", "id": 7, "method": method, "params": {"a": 1}}
    forward, reply = proxy.handle_request(message)
    assert forward == message
    assert reply is None


def test_a_permitted_call_is_forwarded_unchanged(proxy) -> None:
    message = _call("verify", {"sin": "123-456-789"}, purpose="identity_check")
    forward, reply = proxy.handle_request(message)
    assert reply is None
    assert forward["params"]["arguments"] == {"sin": "123-456-789"}


def test_a_call_with_nothing_sensitive_is_forwarded(proxy) -> None:
    message = _call("ping", {"note": "hello"})
    forward, reply = proxy.handle_request(message)
    assert reply is None
    assert forward == message


# ----------------------------------------------------------------------
# Intervene where it matters
# ----------------------------------------------------------------------
def test_a_refused_flow_is_forwarded_with_the_value_removed(proxy) -> None:
    message = _call("track", {"sin": "123-456-789", "page": "/pricing"},
                    purpose="usage_metrics")
    forward, reply = proxy.handle_request(message)
    assert reply is None
    arguments = forward["params"]["arguments"]
    assert "123-456-789" not in json.dumps(arguments)
    assert arguments["page"] == "/pricing"
    assert proxy.redacted == 1


def test_a_denied_flow_never_reaches_the_server(proxy) -> None:
    message = _call("report", {"diagnosis": "Type 2 diabetes"}, purpose="billing")
    forward, reply = proxy.handle_request(message)
    assert forward is None
    assert reply is not None
    assert proxy.blocked == 1


def test_a_refusal_reads_as_a_tool_error_not_a_transport_failure(proxy) -> None:
    """An agent that receives a broken frame retries or dies. One that receives
    an error *result* reads the reason and adapts, which is the behaviour worth
    having.
    """
    _, reply = proxy.handle_request(
        _call("report", {"diagnosis": "Type 2 diabetes"}, request_id=42)
    )
    assert reply["id"] == 42
    assert "error" not in reply           # not a JSON-RPC protocol error
    assert reply["result"]["isError"] is True
    text = reply["result"]["content"][0]["text"]
    assert "AgentLeak" in text
    assert "was not sent" in text


def test_the_refusal_carries_structured_detail_for_the_agent(proxy) -> None:
    _, reply = proxy.handle_request(_call("report", {"diagnosis": "Type 2 diabetes"}))
    detail = reply["result"]["_meta"]["agentleak"]
    assert detail["action"] == "block"
    assert detail["data_types"] == ["health_condition"]
    assert detail["recipient"] == "server"


def test_the_purpose_comes_from_call_metadata(proxy) -> None:
    """Same tool, same arguments, different declared purpose, different answer."""
    _, blocked_reply = proxy.handle_request(
        _call("verify", {"sin": "123-456-789"}, purpose="marketing"))
    forward, _ = proxy.handle_request(
        _call("verify", {"sin": "123-456-789"}, purpose="identity_check"))
    assert blocked_reply is None            # redacted, not blocked
    assert forward["params"]["arguments"] == {"sin": "123-456-789"}


# ----------------------------------------------------------------------
# Wiring
# ----------------------------------------------------------------------
def test_every_decision_lands_in_the_evidence_log(proxy) -> None:
    proxy.handle_request(_call("verify", {"sin": "123-456-789"}, purpose="identity_check"))
    proxy.handle_request(_call("track", {"sin": "123-456-789"}, purpose="metrics"))
    proxy.handle_request(_call("report", {"diagnosis": "Type 2 diabetes"}))
    summary = proxy.gateway.log.summary()
    assert summary["entries"] == 3
    assert summary["verified"] is True


def test_the_recipient_name_comes_from_the_server_command() -> None:
    """Flow rules are written against recipients, so this string is policy
    surface, not a label.
    """
    assert _server_name(["npx", "-y", "@modelcontextprotocol/server-github"]) == "server-github"
    assert _server_name(["/usr/local/bin/my-server", "--port", "3000"]) == "my-server"
    assert _server_name([]) == "mcp"


def test_a_proxy_needs_a_server_command() -> None:
    with pytest.raises(ValueError, match="server command"):
        McpProxy([], gateway=Gateway())


# ----------------------------------------------------------------------
# End to end, through a real subprocess
# ----------------------------------------------------------------------
def test_a_full_session_against_a_real_child_process(tmp_path) -> None:
    """Everything above is unit-level. This runs the whole thing: a child
    server, JSON-RPC over pipes, and the decisions in between.
    """
    server = tmp_path / "server.py"
    server.write_text(textwrap.dedent('''
        import json, sys
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            msg = json.loads(line)
            args = (msg.get("params") or {}).get("arguments")
            sys.stdout.write(json.dumps({
                "jsonrpc": "2.0", "id": msg.get("id"),
                "result": {"echo": args, "method": msg.get("method")},
            }) + "\\n")
            sys.stdout.flush()
    '''))

    requests = "\n".join(json.dumps(m) for m in [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        _call("verify", {"sin": "123-456-789"}, purpose="identity_check", request_id=2),
        _call("track", {"sin": "123-456-789", "page": "/x"}, purpose="metrics", request_id=3),
        _call("report", {"diagnosis": "Type 2 diabetes"}, request_id=4),
    ]) + "\n"

    config = tmp_path / "agentleak.yaml"
    config.write_text(textwrap.dedent("""
        project:
          name: proxy-e2e
        privacy_policy:
          flows:
            - data_type: sin
              to: server
              for: identity_check
            - data_type: health_condition
              to: "*"
              deny: true
    """))

    evidence = tmp_path / "evidence.jsonl"
    completed = subprocess.run(  # noqa: S603
        [
            sys.executable, "-m", "agentleak", "proxy",
            "--config", str(config),
            "--evidence", str(evidence), "--recipient", "server", "--quiet",
            "--", sys.executable, str(server),
        ],
        input=requests, capture_output=True, text=True, timeout=60,
    )

    replies = {
        json.loads(line)["id"]: json.loads(line)
        for line in completed.stdout.splitlines() if line.strip()
    }
    assert replies[1]["result"]["method"] == "initialize"
    assert replies[2]["result"]["echo"]["sin"] == "123-456-789"      # allowed
    assert "123-456-789" not in json.dumps(replies[3]["result"])      # redacted
    assert replies[4]["result"]["isError"] is True                    # blocked

    from agentleak.core.evidence import verify
    assert verify(evidence).ok
