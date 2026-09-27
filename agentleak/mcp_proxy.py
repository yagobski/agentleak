# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Sit between an agent and its MCP servers, and judge every call on the way out.

MCP is where agents reach the outside world in 2026, and it is where the year's
incidents happened: tool poisoning, name collisions sending data to the wrong
tool, confused parameter mapping posting a record to the wrong endpoint. Every
one of those is the same sentence — *sensitive data went to the wrong recipient
through a tool call* — which is the sentence this project is built around. And
AgentLeak's MCP support was a converter you fed a log you already had.

This is the other half. It speaks MCP on both sides: the agent launches it as
its server, it launches the real server as a child, and it forwards the JSON-RPC
between them. `tools/call` is the one message it does not simply pass along —
that one goes to the :class:`~agentleak.defenses.gateway.Gateway` first, which
allows it, rewrites its arguments, or refuses it, and appends the decision to a
hash-chained evidence log.

    agentleak proxy --evidence evidence.jsonl -- npx -y @modelcontextprotocol/server-github

Two properties matter more than features here.

**A blocked call must look like a normal tool error, not a transport failure.**
An agent that receives a broken frame retries, or dies. One that receives an
error result reads the reason and adapts — which is the behaviour you want, and
the reason the refusal carries a structured explanation rather than a code.

**Anything the proxy does not understand is forwarded unchanged.** It is on the
critical path of somebody's agent. A proxy that half-implements MCP breaks
sessions in ways nobody can debug, so every message that is not a `tools/call`
crosses untouched, in both directions, including notifications and errors.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from typing import Any, TextIO

from .defenses.gateway import Action, Gateway

__all__ = ["McpProxy", "run_proxy"]


# Wrappers that launch the real server rather than being it. Naming the
# wrapper would put "npx" in everybody's policy.
_RUNNERS = {
    "npx", "npm", "pnpm", "yarn", "bunx", "bun",
    "node", "deno", "python", "python3", "uv", "uvx", "pipx", "docker",
}


def _server_name(command: list[str]) -> str:
    """A stable recipient name for the server behind this proxy.

    Flow rules are written against recipients, so this string is policy surface,
    not a label: get it wrong and every rule silently stops matching. Scanning
    is forward and skips wrappers and flags, because scanning backward picks up
    an option's *value* — ``["my-server", "--port", "3000"]`` would be named
    "3000". Pass ``--recipient`` when the guess is wrong.
    """
    for part in command:
        if not part or part.startswith("-"):
            continue
        base = part.rsplit("/", 1)[-1]
        if base.lower() in _RUNNERS or base.lower().rstrip("0123456789.") in _RUNNERS:
            continue
        return base
    return "mcp"


class McpProxy:
    """JSON-RPC passthrough with a policy decision on ``tools/call``."""

    def __init__(
        self,
        command: list[str],
        *,
        gateway: Gateway,
        recipient: str = "",
        verbose: bool = False,
        inspect_responses: bool = False,
        agent: str = "mcp-client",
    ) -> None:
        if not command:
            raise ValueError("a proxy needs a server command to forward to")
        self.command = command
        self.gateway = gateway
        self.recipient = recipient or _server_name(command)
        self.verbose = verbose
        self.inspect_responses = inspect_responses
        self.agent = agent
        self.blocked = 0
        self.redacted = 0
        self.allowed = 0
        # tools/call ids in flight -> (tool, purpose), so a result can be judged
        # as the flow it is: from this server, to the agent, for that purpose.
        self._pending: dict[Any, tuple[str, str]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def _note(self, message: str) -> None:
        # stderr only: stdout is the JSON-RPC channel, and one stray line on it
        # corrupts the session.
        if self.verbose:
            print(f"[agentleak] {message}", file=sys.stderr, flush=True)

    def _refusal(self, request_id: Any, decision: Any) -> dict[str, Any]:
        """A refusal shaped as a tool result, so the agent can read and adapt.

        `isError` on a result rather than a JSON-RPC error: the call reached a
        tool and the tool declined, which is a fact about the request, not a
        malfunction of the transport.
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "isError": True,
                "content": [{
                    "type": "text",
                    "text": (
                        "Blocked by AgentLeak privacy policy: "
                        f"{decision.reason}\n\n"
                        "This call was not sent. Remove the personal data from "
                        "the arguments, or route it to a recipient the policy "
                        "permits, and try again."
                    ),
                }],
                "_meta": {"agentleak": decision.to_dict()},
            },
        }

    # ------------------------------------------------------------------
    def handle_request(self, message: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Judge one client message.

        Returns ``(forward, reply)``: the message to send to the server, and a
        message to send straight back to the client. Exactly one is not None.
        """
        if message.get("method") != "tools/call":
            return message, None

        params = message.get("params") or {}
        tool = str(params.get("name") or "")
        arguments = params.get("arguments")
        meta = params.get("_meta") or {}
        purpose = str(meta.get("purpose") or meta.get("agentleak/purpose") or "")

        decision = self.gateway.check(
            arguments,
            tool=f"{self.recipient}/{tool}" if tool else self.recipient,
            recipient=self.recipient,
            purpose=purpose,
        )
        if decision.action != Action.BLOCK and "id" in message:
            with self._lock:
                self._pending[message["id"]] = (tool, purpose)

        if decision.action == Action.BLOCK:
            self.blocked += 1
            self._note(f"BLOCK {tool}: {decision.reason}")
            return None, self._refusal(message.get("id"), decision)

        if decision.action == Action.REDACT:
            self.redacted += 1
            self._note(f"REDACT {tool}: {decision.reason}")
            forwarded = json.loads(json.dumps(message))
            forwarded.setdefault("params", {})["arguments"] = decision.arguments
            return forwarded, None

        self.allowed += 1
        return message, None

    # ------------------------------------------------------------------
    def handle_response(self, message: dict[str, Any]) -> dict[str, Any]:
        """Judge one server message on its way back to the agent.

        Only results of a ``tools/call`` this proxy forwarded are touched, and
        only when response inspection is on: a result carries data *into* the
        agent's context, which is where minimisation has to happen, but turning
        it on changes what an existing policy means (an ``allow`` for ``sin`` to
        a KYC server says nothing about the SIN it sends back), so it is opt-in.

        Tokens this proxy issued are put back last. They stand for values the
        agent itself sent, so they are not new data flowing to it.
        """
        with self._lock:
            pending = self._pending.pop(message.get("id"), None) if "id" in message else None
        if pending is None or "result" not in message:
            return self._restore(message)

        tool, purpose = pending
        if self.inspect_responses:
            result = message["result"]
            decision = self.gateway.check(
                result,
                tool=f"{self.recipient}/{tool}" if tool else self.recipient,
                recipient=self.agent,
                sender=self.recipient,
                purpose=purpose,
                direction="response",
            )
            if decision.action == Action.BLOCK:
                self.blocked += 1
                self._note(f"WITHHOLD {tool} result: {decision.reason}")
                message = {**message, "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": (
                        "The tool ran, but AgentLeak withheld its result under the "
                        f"privacy policy: {decision.reason}"
                    )}],
                    "_meta": {"agentleak": decision.to_dict()},
                }}
            elif decision.action == Action.REDACT:
                self.redacted += 1
                self._note(f"REDACT {tool} result: {decision.reason}")
                message = {**message, "result": decision.arguments}
        return self._restore(message)

    def _restore(self, message: dict[str, Any]) -> dict[str, Any]:
        tokenizer = self.gateway.sanitizer.tokenizer
        if tokenizer is None or len(tokenizer) == 0:
            return message
        restored = tokenizer.restore_obj(message)
        return restored if isinstance(restored, dict) else message

    @property
    def _rewrites_responses(self) -> bool:
        return self.inspect_responses or self.gateway.sanitizer.tokenizer is not None

    # ------------------------------------------------------------------
    def run(self, stdin: TextIO | None = None, stdout: TextIO | None = None) -> int:
        """Run until the client closes stdin or the server exits."""
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout

        server = subprocess.Popen(  # noqa: S603 - the command is the user's own
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            bufsize=1,
        )
        assert server.stdin and server.stdout
        self._note(f"proxying {' '.join(self.command)} as recipient '{self.recipient}'")

        def pump_server_to_client() -> None:
            # Server -> client passes through untouched unless responses are
            # inspected or tokens need restoring; even then only messages that
            # parse are rewritten, and the rest cross byte for byte.
            try:
                for line in server.stdout:  # type: ignore[union-attr]
                    if self._rewrites_responses and line.strip():
                        try:
                            message = json.loads(line)
                        except json.JSONDecodeError:
                            message = None
                        if isinstance(message, dict):
                            line = json.dumps(self.handle_response(message)) + "\n"
                    stdout.write(line)
                    stdout.flush()
            except (BrokenPipeError, ValueError):
                pass

        reader = threading.Thread(target=pump_server_to_client, daemon=True)
        reader.start()

        try:
            for line in stdin:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    message = json.loads(stripped)
                except json.JSONDecodeError:
                    # Not ours to interpret. Forward it and let the server say so.
                    server.stdin.write(line)
                    server.stdin.flush()
                    continue

                forward, reply = self.handle_request(message)
                if reply is not None:
                    stdout.write(json.dumps(reply) + "\n")
                    stdout.flush()
                    continue
                if forward is not None:
                    server.stdin.write(json.dumps(forward) + "\n")
                    server.stdin.flush()
        except (BrokenPipeError, KeyboardInterrupt):
            pass
        finally:
            try:
                server.stdin.close()
            except Exception:  # noqa: BLE001
                pass
            server.wait(timeout=10)
            self._note(
                f"session ended — {self.allowed} allowed, "
                f"{self.redacted} redacted, {self.blocked} blocked"
            )
        return server.returncode or 0


def run_proxy(
    command: list[str],
    *,
    flows: Any = None,
    evidence: str | None = None,
    recipient: str = "",
    block_on_violation: bool = False,
    verbose: bool = False,
    inspect_responses: bool = False,
    style: str = "placeholder",
    agent: str = "mcp-client",
    groups: dict[str, Any] | None = None,
    sign_key: str | None = None,
) -> int:
    gateway = Gateway(
        flows=flows,
        groups=groups,
        sign_key=sign_key,
        evidence=evidence,
        block_on_violation=block_on_violation,
        agent=agent,
        redaction_style=style,
    )
    return McpProxy(
        command, gateway=gateway, recipient=recipient, verbose=verbose,
        inspect_responses=inspect_responses, agent=agent,
    ).run()
