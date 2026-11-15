# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""A deliberately leaky toy agent that speaks the self-test protocol.

It does what careless agents do: the final answer is polite and clean, while
the full private record goes into a tool call, a handoff, memory, a log line
and a generated file. All data it handles is synthetic, issued by
``agentleak selftest --cmd``.

Its only configuration is ``agent_config.json`` (or ``$LEAKY_AGENT_CONFIG``)::

    {"sanitize": ["log"], "extra_patterns": {"medical_record_number": "MRN-\\\\d{8}"}}

``sanitize`` lists the channels whose outbound content goes through
``agentleak.defenses.Sanitizer`` first; ``extra_patterns`` are passed to it.
``fix_loop.py`` edits this file from the self-test's ``next_steps[].fix``.

Run it by hand::

    agentleak selftest --cmd "python examples/selftest/leaky_agent.py"
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from agentleak.defenses import Sanitizer
from agentleak.selftest.adapter import Reporter, read_scenario

CONFIG = Path(os.environ.get("LEAKY_AGENT_CONFIG", Path(__file__).with_name("agent_config.json")))


def load_config() -> dict[str, Any]:
    if CONFIG.is_file():
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    return {"sanitize": [], "extra_patterns": {}}


def main() -> None:
    config = load_config()
    sanitizer = Sanitizer(extra_patterns=config.get("extra_patterns") or None)
    guarded = set(config.get("sanitize") or [])

    def out(channel: str, value: Any) -> Any:
        """The agent's own boundary: redact here when the config says so."""
        if channel not in guarded:
            return value
        if isinstance(value, dict):
            return sanitizer.sanitize_dict(value)
        return sanitizer.sanitize(str(value))

    scenario = read_scenario()
    report = Reporter(agent="toy_agent")
    record: dict[str, str] = scenario["records"][0]["fields"]
    flat = ", ".join(f"{k}={v}" for k, v in record.items())

    # 1. Call a downstream tool with the whole record ("it might need it").
    report.tool_call("ticketing.create", out("tool_call", {"summary": scenario["title"], **record}))
    # 2. Hand the whole record to a helper agent.
    report.message("helper_agent", out("inter_agent_message", f"Please handle this: {flat}"))
    # 3. Remember the contact details for next time.
    report.memory(out("shared_memory", f"last customer: {flat}"), key="session_memory")
    # 4. Debug log of the full payload.
    report.log(out("log", f"DEBUG processing record {json.dumps(record)}"))
    # 5. Write a working note to disk.
    report.file("notes.md", out("generated_file", f"# Notes\n\n{flat}\n"))
    # 6. A clean, polite answer. Output-only audits stop here and see nothing.
    report.final(out("final_output", "Done. I have completed the task."))


if __name__ == "__main__":
    main()
