# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""The other half of a tool call, and a pseudonym instead of a hole.

Until 0.16 the proxy judged what an agent sent and passed back whatever the
server returned. A tool result is data flowing *into* the agent's context, and
minimisation has to happen there too: Lasso's gateway masks both directions.
Response inspection is opt-in because it changes what an existing policy
means, and these tests pin both the default and the opt-in.

Tokens replace a value with a stable keyed pseudonym, so two calls about the
same customer still refer to the same customer, and the proxy puts the real
value back on the way to the agent that sent it.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

from agentleak.defenses import sanitize_text
from agentleak.defenses.gateway import Action, Gateway
from agentleak.defenses.tokenizer import TOKEN_RE, Tokenizer
from agentleak.mcp_proxy import McpProxy

SIN = "046 454 286"
POLICY = [
    {"data_type": "sin", "to": "kyc", "for": "identity_check"},
    {"data_type": "health_condition", "to": "*", "deny": True},
]


def _proxy(tmp_path, **kwargs) -> McpProxy:
    style = kwargs.pop("style", "placeholder")
    gateway = Gateway(flows=POLICY, evidence=str(tmp_path / "e.jsonl"),
                      agent="client", redaction_style=style)
    return McpProxy(["echo"], gateway=gateway, recipient="crm", agent="client", **kwargs)


def _call(arguments: dict, request_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
            "params": {"name": "lookup", "arguments": arguments}}


def _result(content: str, request_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": request_id,
            "result": {"content": [{"type": "text", "text": content}]}}


# ----------------------------------------------------------------------
# Responses
# ----------------------------------------------------------------------
def test_responses_pass_untouched_by_default(tmp_path):
    proxy = _proxy(tmp_path)
    proxy.handle_request(_call({"q": "customer 4812"}))
    reply = _result(f"customer SIN {SIN}")
    assert proxy.handle_response(reply) == reply


def test_an_inspected_response_is_redacted_when_the_flow_is_not_permitted(tmp_path):
    proxy = _proxy(tmp_path, inspect_responses=True)
    proxy.handle_request(_call({"q": "customer 4812"}))
    out = proxy.handle_response(_result(f"customer SIN {SIN}, tier gold"))
    text = out["result"]["content"][0]["text"]
    assert SIN not in text and "tier gold" in text


def test_a_denied_type_in_a_response_is_withheld_with_a_readable_reason(tmp_path):
    proxy = _proxy(tmp_path, inspect_responses=True)
    proxy.handle_request(_call({"q": "patient 17"}))
    out = proxy.handle_response(_result("diagnosis: Type 2 diabetes"))
    assert out["result"]["isError"] is True
    assert "withheld" in out["result"]["content"][0]["text"]
    assert out["result"]["_meta"]["agentleak"]["direction"] == "response"


def test_only_results_of_forwarded_calls_are_judged(tmp_path):
    proxy = _proxy(tmp_path, inspect_responses=True)
    # No matching tools/call in flight: a notification or an unrelated reply.
    note = {"jsonrpc": "2.0", "method": "notifications/message",
            "params": {"data": f"SIN {SIN}"}}
    assert proxy.handle_response(note) == note


def test_response_decisions_are_in_the_evidence_log(tmp_path):
    proxy = _proxy(tmp_path, inspect_responses=True)
    proxy.handle_request(_call({"q": "c"}))
    proxy.handle_response(_result(f"SIN {SIN}"))
    lines = [json.loads(x) for x in (tmp_path / "e.jsonl").read_text().splitlines()]
    assert lines[-1]["metadata"]["direction"] == "response"
    assert lines[-1]["recipient"] == "client"


# ----------------------------------------------------------------------
# Tokens
# ----------------------------------------------------------------------
def test_the_same_value_gets_the_same_token():
    tok = Tokenizer(key=b"k")
    assert tok.token(SIN, "sin") == tok.token(SIN, "sin")
    assert tok.token(SIN, "sin") != tok.token("046 454 287", "sin")
    assert TOKEN_RE.fullmatch(tok.token(SIN, "sin"))


def test_tokens_depend_on_the_key():
    assert Tokenizer(key=b"a").token(SIN, "sin") != Tokenizer(key=b"b").token(SIN, "sin")


def test_redact_token_style_keeps_references_stable():
    out = sanitize_text(f"first {SIN}, again {SIN}", style="token")
    tokens = TOKEN_RE.findall(out)
    assert SIN not in out and len(tokens) == 2 and tokens[0] == tokens[1]


def test_only_issued_tokens_are_restored():
    tok = Tokenizer(key=b"k")
    issued = tok.token(SIN, "sin")
    foreign = "[[SIN:0123456789]]"
    assert tok.restore(f"{issued} {foreign}") == f"{SIN} {foreign}"


def test_the_server_sees_a_token_and_the_agent_gets_the_value_back(tmp_path):
    proxy = _proxy(tmp_path, style="token")
    forward, reply = proxy.handle_request(_call({"sin": SIN, "note": "open ticket"}))
    assert reply is None
    sent = forward["params"]["arguments"]["sin"]
    assert SIN not in json.dumps(forward) and TOKEN_RE.fullmatch(sent)
    echoed = proxy.handle_response(_result(f"ticket opened for {sent}"))
    assert echoed["result"]["content"][0]["text"] == f"ticket opened for {SIN}"


def test_a_token_is_never_written_to_the_evidence_log(tmp_path):
    proxy = _proxy(tmp_path, style="token")
    proxy.handle_request(_call({"sin": SIN}))
    assert SIN not in (tmp_path / "e.jsonl").read_text()


def test_gateway_token_style_is_consistent_across_calls():
    gw = Gateway(flows=POLICY, redaction_style="token")
    a = gw.check({"sin": SIN}, recipient="crm")
    b = gw.check({"customer": SIN}, recipient="crm")
    assert a.action == b.action == Action.REDACT
    assert a.arguments["sin"] == b.arguments["customer"]


# ----------------------------------------------------------------------
# End to end
# ----------------------------------------------------------------------
@pytest.mark.parametrize("flags, expect_restored", [(["--style", "token"], True), ([], False)])
def test_token_round_trip_through_a_real_child_process(tmp_path, flags, expect_restored):
    server = tmp_path / "server.py"
    received = tmp_path / "server_received.txt"
    server.write_text(textwrap.dedent(f'''
        import json, sys
        log = open({str(received)!r}, "a")
        seen = []
        for line in sys.stdin:
            if not line.strip():
                continue
            msg = json.loads(line)
            args = (msg.get("params") or {{}}).get("arguments") or {{}}
            seen.append(args.get("sin"))
            log.write(str(args.get("sin")) + "\\n"); log.flush()
            sys.stdout.write(json.dumps({{"jsonrpc": "2.0", "id": msg.get("id"), "result": {{
                "content": [{{"type": "text", "text": "stored " + str(args.get("sin"))}}]}}}}) + "\\n")
            sys.stdout.flush()
    '''))
    config = tmp_path / "agentleak.yaml"
    config.write_text("privacy_policy:\n  flows:\n    - data_type: sin\n      to: kyc\n")
    requests = "\n".join(json.dumps(_call({"sin": SIN}, i)) for i in (1, 2)) + "\n"
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "agentleak", "proxy", "--config", str(config),
         "--evidence", str(tmp_path / "e.jsonl"), "--recipient", "crm", "--quiet", *flags,
         "--", sys.executable, str(server)],
        input=requests, capture_output=True, text=True, timeout=60,
    )
    replies = [json.loads(x) for x in completed.stdout.splitlines() if x.strip()]
    assert len(replies) == 2, completed.stderr
    text = replies[0]["result"]["content"][0]["text"]
    assert (SIN in text) is expect_restored
    if expect_restored:
        # Restored for the agent; the server only ever held the token, the same
        # token both times, and neither log holds the value.
        held = received.read_text().split()
        assert SIN not in received.read_text()
        assert len(held) == 2 and held[0] == held[1] and TOKEN_RE.fullmatch(held[0])
        assert SIN not in (tmp_path / "e.jsonl").read_text()
