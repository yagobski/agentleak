# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Reference adapter for ``agentleak selftest --cmd``: the agent's side of the protocol.

Standard library only, so an agent can also copy this file instead of importing
it. Minimal use::

    from agentleak.selftest.adapter import read_scenario, Reporter

    scenario = read_scenario()          # stdin, or $AGENTLEAK_SCENARIO_FILE
    report = Reporter()                 # writes JSON lines to stdout
    record = scenario["records"][0]["fields"]

    report.tool_call("crm.update", {"note": "..."})
    report.memory("case summary ...")
    report.log("handled request")
    report.message("scheduler", "please book ...")
    report.file("referral.md", "...")
    report.final("Done.")

Report what your agent actually sent, wrote or said, at the boundary where it
happens: the self-test scores exactly what you report. Reporting a cleaned-up
version of what was really sent would make the result meaningless.

Run ``agentleak selftest --cmd "python my_agent.py"``.
"""

from __future__ import annotations

import json
import os
import sys
from typing import IO, Any

PROTOCOL = "agentleak.selftest.v1"


def in_selftest() -> bool:
    """True when this process was started by ``agentleak selftest --cmd``."""
    return os.environ.get("AGENTLEAK_SELFTEST") == "1"


def read_scenario(stream: IO[str] | None = None) -> dict[str, Any]:
    """The scenario this run must handle (the ``scenario`` object of the document)."""
    path = os.environ.get("AGENTLEAK_SCENARIO_FILE")
    if stream is None and path and os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    else:
        doc = json.loads((stream or sys.stdin).read())
    if doc.get("protocol") != PROTOCOL:
        raise ValueError(f"expected protocol {PROTOCOL!r}, got {doc.get('protocol')!r}")
    scenario: dict[str, Any] = doc["scenario"]
    return scenario


class Reporter:
    """Writes one event per line in the format the self-test reads."""

    def __init__(self, stream: IO[str] | None = None, *, agent: str = "agent") -> None:
        self.stream = stream or sys.stdout
        self.agent = agent

    def emit(self, channel: str, content: Any, *, target: str = "", **metadata: Any) -> None:
        event: dict[str, Any] = {"channel": channel, "content": content,
                                 "source": self.agent, "target": target or channel}
        if metadata:
            event["metadata"] = metadata
        self.stream.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        self.stream.flush()

    def tool_call(self, tool: str, arguments: Any) -> None:
        self.emit("tool_call", arguments, target=tool)

    def message(self, to_agent: str, content: Any) -> None:
        self.emit("inter_agent_message", content, target=to_agent)

    def memory(self, content: Any, *, key: str = "memory") -> None:
        self.emit("shared_memory", content, target=key)

    def log(self, content: Any, *, logger: str = "log") -> None:
        self.emit("log", content, target=logger)

    def file(self, path: str, content: Any) -> None:
        self.emit("generated_file", content, target=path)

    def final(self, content: Any) -> None:
        self.emit("final_output", content, target="user")


__all__ = ["PROTOCOL", "Reporter", "in_selftest", "read_scenario"]
