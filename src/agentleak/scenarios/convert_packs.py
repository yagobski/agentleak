# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Converters for the multi-agent and MCP scenario packs.

* **AgentSocialBench** (``kingofspace0wzz/agentsocialbench``, MIT): agents that
  each serve one person hand work to each other. A record names the sender
  agent, the private context it holds, the recipient (another agent, a group
  chat or a shared plan) and the statements that must not cross. The leaking
  trace carries two of those statements in the hand-off; the clean variant
  carries the source's acceptable abstractions instead.
* **MCPTox** (``zhiqiangwang4/MCPTox-Benchmark``, data CC-BY-4.0): a tool
  description on an MCP server carries a planted instruction, and a model's
  recorded call sends the user's data to a recipient the description named.
  The clean variant is the recorded call of a model that ignored it.

Both are pure and deterministic. A record with ``"variant": "clean"`` converts
to its clean counterpart; the canaries stay the same, so the counterpart can
be scored against the very ground truth it must not disclose.
"""

from __future__ import annotations

import re
from typing import Any

from ..core.trace import Trace


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_") or "agent"


def _render_args(args: dict[str, Any]) -> str:
    parts = []
    for key, value in args.items():
        if isinstance(value, dict):
            value = ", ".join(f"{k}: {v}" for k, v in value.items())
        elif isinstance(value, (list, tuple)):
            value = ", ".join(str(v) for v in value)
        parts.append(f"{key}: {value}")
    return "\n".join(parts)


def split_canaries(values: list[Any]) -> dict[str, list[str]]:
    """Prose goes to the semantic tier, single tokens to the realistic tier."""
    realistic: list[str] = []
    semantic: list[str] = []
    for value in values:
        text = str(value).strip()
        if text:
            (semantic if " " in text else realistic).append(text)
    return {"realistic": realistic, "semantic": semantic}


def is_clean(record: dict[str, Any]) -> bool:
    return str(record.get("variant") or "") == "clean"


# ----------------------------------------------------------------------
# AgentSocialBench
# ----------------------------------------------------------------------
def agentsocialbench_to_trace(record: dict[str, Any]) -> Trace:
    """One hand-off between agents that serve different people (or domains).

    The private context enters on ``tool_response`` (a source). The hand-off is
    the disclosure: ``inter_agent_message`` to another agent, or
    ``shared_memory`` for a group chat or plan every member agent reads.
    """
    sender = record.get("sender") or {}
    recipient = record.get("recipient") or {}
    sender_agent = str(sender.get("agent") or "sender_agent")
    recipient_agent = str(recipient.get("agent") or "recipient_agent")
    user = str(sender.get("user") or "user")
    rid = str(record.get("id") or "agentsocialbench")
    trace = Trace(run_id=f"trace_{_slug(rid)}", agent_name=sender_agent, scenario_id=rid)

    trace.add_event(
        "user_input", str(record.get("task") or "").strip(),
        source=user, target=sender_agent,
    )
    trace.add_event(
        "tool_response",
        "\n".join(str(line) for line in record.get("private_context") or []),
        source=f"{_slug(user)}_private_memory", target=sender_agent,
        metadata={"tool_name": "private_memory", "data_subject": record.get("data_subject", "")},
    )
    carried = record.get("abstractions") if is_clean(record) else record.get("leaked_values")
    body = [str(s) for s in record.get("shared_content") or []] + [str(c) for c in carried or []]
    metadata: dict[str, Any] = {
        "recipient": recipient_agent,
        "data_subject": record.get("data_subject", ""),
        "transmission_principle": record.get("transmission_principle", ""),
        "category": record.get("category", ""),
    }
    if recipient.get("audience"):
        metadata["audience"] = list(recipient["audience"])
    if record.get("affinity"):
        metadata["affinity"] = dict(record["affinity"])
    trace.add_event(
        str(record.get("channel") or "inter_agent_message"),
        "\n".join(body),
        source=sender_agent, target=recipient_agent,
        metadata=metadata,
    )
    trace.add_event(
        "final_output", f"Done. I sent my part to {recipient_agent}.",
        source=sender_agent, target=user,
    )
    return trace


def agentsocialbench_metadata(record: dict[str, Any]) -> dict[str, Any]:
    category = str(record.get("category") or "multi-agent")
    sender = (record.get("sender") or {}).get("agent", "an agent")
    recipient = (record.get("recipient") or {}).get("agent", "another agent")
    return {
        "name": str(record.get("id") or "AgentSocialBench scenario"),
        "domain": category,
        "description": (
            f"{sender} passes facts about {record.get('data_subject') or 'its user'} that must "
            f"not cross to {recipient} on {record.get('channel', 'inter_agent_message')}."
        ),
        "sensitive_data": [str(v)[:60] for v in (record.get("leaked_values") or [])[:5]],
        "tags": [
            "agentsocialbench", "multi-agent", "contextual-integrity",
            f"category:{category}", f"channel:{record.get('channel', '')}",
            *([f"sub-type:{record['sub_type']}"] if record.get("sub_type") else []),
            *(["clean-counterpart"] if is_clean(record) else []),
        ],
        "difficulty": "",
        "canaries": split_canaries(list(record.get("leaked_values") or [])),
    }


# ----------------------------------------------------------------------
# MCPTox
# ----------------------------------------------------------------------
def mcptox_to_trace(record: dict[str, Any]) -> Trace:
    """A poisoned tool description redirects a legitimate MCP tool call.

    The tool list (with the planted description) arrives on ``tool_response``;
    the call is a ``tool_call`` whose ``target`` is the recipient it addresses,
    so a flow rule can judge where the user's data went.
    """
    server = str(record.get("server") or "mcp")
    rid = str(record.get("id") or "mcptox")
    trace = Trace(run_id=f"trace_{_slug(rid)}", agent_name="mcp_assistant", scenario_id=rid)
    trace.add_event(
        "user_input", str(record.get("user_prompt") or "").strip(),
        source="user", target="assistant",
    )
    poisoned = record.get("poisoned_tool") or {}
    listing = (
        f"Tools on {server}: {', '.join(record.get('legitimate_tools') or [])}\n\n"
        f"{poisoned.get('description', '')}"
    )
    trace.add_event(
        "tool_response", listing,
        source=f"mcp:{server}", target="assistant",
        metadata={"tool_name": "tools/list", "mcp_server": server, "prompt_injection": True},
    )
    clean = is_clean(record)
    call = (record.get("clean_call") if clean else record.get("hijacked_call")) or {}
    tool = str(call.get("tool") or "tool")
    trace.add_event(
        "tool_call", _render_args(dict(call.get("args") or {})),
        source="assistant", target=str(call.get("recipient") or tool),
        metadata={
            "tool_name": tool,
            "mcp_server": server,
            "recorded_from_model": call.get("model", ""),
            "attacker_controlled": not clean,
        },
    )
    trace.add_event("final_output", "Done.", source="assistant", target="user")
    return trace


def mcptox_metadata(record: dict[str, Any]) -> dict[str, Any]:
    server = str(record.get("server") or "mcp")
    return {
        "name": str(record.get("id") or "MCPTox scenario"),
        "domain": server,
        "description": (
            f"A planted instruction in the description of {(record.get('poisoned_tool') or {}).get('name', 'a tool')} "
            f"on the {server} MCP server sends the user's data to {record.get('attacker_recipient', 'another recipient')}."
        ),
        "sensitive_data": [str(v)[:60] for v in (record.get("leaked_values") or [])[:5]],
        "tags": [
            "mcptox", "mcp", "tool-poisoning", "prompt-injection",
            f"server:{server}", f"security-risk:{record.get('security_risk', '')}",
            *(["clean-counterpart"] if is_clean(record) else []),
        ],
        "difficulty": "",
        "canaries": split_canaries(list(record.get("leaked_values") or [])),
    }


__all__ = [
    "agentsocialbench_metadata",
    "agentsocialbench_to_trace",
    "is_clean",
    "mcptox_metadata",
    "mcptox_to_trace",
    "split_canaries",
]
