# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Concrete fix objects for each leaking channel.

``CHANNEL_REMEDIATION`` in :mod:`agentleak.core.report` already carries a short
piece of advice and a generic, dependency-free ``code_fix`` per channel; the
self-test keeps both (same names, same meaning as ``/api/agent/improve``). What
it adds is a ``fix`` object an agent can act on without parsing prose: which
AgentLeak defense to apply, at which boundary, with what settings, and a
snippet that uses the real API.

Every snippet below calls only public, existing AgentLeak API
(:class:`agentleak.defenses.Sanitizer`, ``sanitize`` / ``sanitize_dict``), and
the test-suite executes each one.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

SANITIZER = "agentleak.defenses.Sanitizer"

# Where each channel's boundary is, in words an agent can map to its own code.
_WHERE: dict[str, str] = {
    "tool_call": "the arguments of every outbound tool or API call, just before the call is made",
    "inter_agent_message": "every message or handoff payload sent to another agent",
    "shared_memory": "every value written to memory, a scratchpad, a vector store or a cache",
    "log": "every string written to a log, a trace exporter or stdout/stderr",
    "generated_file": "the content of every file, report or artifact the agent writes",
    "final_output": "the final answer, just before it is returned to the user",
}

_CODE: dict[str, str] = {
    "tool_call": (
        "from agentleak.defenses import Sanitizer\n"
        "\n"
        "_sanitizer = Sanitizer()\n"
        "\n"
        "def safe_args(args: dict) -> dict:\n"
        "    \"\"\"Redact sensitive values before they leave in a tool call.\"\"\"\n"
        "    return _sanitizer.sanitize_dict(args)\n"
        "\n"
        "# before: call_tool(name, args)\n"
        "# after:  call_tool(name, safe_args(args))\n"
    ),
    "inter_agent_message": (
        "from agentleak.defenses import Sanitizer\n"
        "\n"
        "_sanitizer = Sanitizer()\n"
        "\n"
        "def safe_handoff(text: str) -> str:\n"
        "    \"\"\"Send the next agent what it needs, not the raw record.\"\"\"\n"
        "    return _sanitizer.sanitize(text)\n"
        "\n"
        "# before: send_to_agent(peer, message)\n"
        "# after:  send_to_agent(peer, safe_handoff(message))\n"
    ),
    "shared_memory": (
        "from agentleak.defenses import Sanitizer\n"
        "\n"
        "_sanitizer = Sanitizer()\n"
        "\n"
        "def safe_memory(value: str) -> str:\n"
        "    \"\"\"Never persist raw identifiers; store the redacted form.\"\"\"\n"
        "    return _sanitizer.sanitize(value)\n"
        "\n"
        "# before: memory[key] = value\n"
        "# after:  memory[key] = safe_memory(value)\n"
    ),
    "log": (
        "from agentleak.defenses import Sanitizer\n"
        "\n"
        "_sanitizer = Sanitizer()\n"
        "\n"
        "def safe_log(message: str) -> str:\n"
        "    \"\"\"Redact at the logging boundary; never log full payloads.\"\"\"\n"
        "    return _sanitizer.sanitize(message)\n"
        "\n"
        "# before: logger.info(message)\n"
        "# after:  logger.info(safe_log(message))\n"
    ),
    "generated_file": (
        "from agentleak.defenses import Sanitizer\n"
        "\n"
        "_sanitizer = Sanitizer()\n"
        "\n"
        "def safe_document(content: str) -> str:\n"
        "    \"\"\"Redact a document before it is written or exported.\"\"\"\n"
        "    return _sanitizer.sanitize(content)\n"
        "\n"
        "# before: path.write_text(content)\n"
        "# after:  path.write_text(safe_document(content))\n"
    ),
    "final_output": (
        "from agentleak.defenses import Sanitizer\n"
        "\n"
        "_sanitizer = Sanitizer()\n"
        "\n"
        "def safe_answer(text: str) -> str:\n"
        "    \"\"\"Last-mile guardrail on the answer the user sees.\"\"\"\n"
        "    return _sanitizer.sanitize(text)\n"
        "\n"
        "# before: return answer\n"
        "# after:  return safe_answer(answer)\n"
    ),
}

#: Channel -> fix object. ``type`` is always ``apply_defense`` for runtime
#: leaks; ``settings`` are keyword arguments for the defense's constructor.
CHANNEL_FIXES: dict[str, dict[str, Any]] = {
    channel: {
        "type": "apply_defense",
        "defense": SANITIZER,
        "channel": channel,
        "where": _WHERE[channel],
        "settings": {"style": "placeholder"},
        "code": _CODE[channel],
        "docs": "docs/defenses.md",
        "also_consider": (
            "Data minimization: pass only the fields the step needs. Redaction "
            "is the fallback when the value itself is not needed downstream."
        ),
    }
    for channel in _WHERE
}


def fix_for_channel(channel: str) -> dict[str, Any] | None:
    """A fresh copy of the fix object for ``channel``, or ``None`` for a source."""
    fix = CHANNEL_FIXES.get(channel)
    return deepcopy(fix) if fix else None


def fix_for_code_finding(finding: dict[str, Any]) -> dict[str, Any]:
    """Fix object for a static code-scan finding."""
    return {
        "type": "code_change",
        "file": finding.get("file"),
        "line": finding.get("line"),
        "rule": finding.get("rule"),
        "suggestion": finding.get("fix") or "",
        "docs": "docs/code-scan.md",
    }


__all__ = ["CHANNEL_FIXES", "SANITIZER", "fix_for_channel", "fix_for_code_finding"]
