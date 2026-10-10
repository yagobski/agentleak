# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Turn a Claude Code sub-agent transcript into an AgentLeak trace.

Claude Code writes one JSONL file per sub-agent, next to the session:

    ~/.claude/projects/<project>/<session>/subagents/agent-<id>.jsonl

That file keeps every tool result in full, whatever the sub-agent chose to say
in its report. Run it:

    python examples/claude_code_transcript.py                      # bundled sample
    python examples/claude_code_transcript.py agent-x.jsonl out.json

How a transcript is spread over the channels:

    task given to the sub-agent      inter_agent_message   main_agent -> subagent
    non-empty thinking               log                   subagent -> reasoning
    tool call                        tool_call             subagent -> resource
    tool result                      tool_response         resource -> subagent
    report back                      inter_agent_message   subagent -> main_agent
    the transcript file itself       generated_file        subagent -> transcript_on_disk

"resource" is the tool name unless ``resource_of`` says otherwise. Naming it is
where the judgement lives: flow rules with an ``origin`` only work if a read of
the store is recorded as coming from the store, not from ``Bash``. The sample
``resource_of`` below follows one indirection (the agent writes a script that
opens the store, then runs it); it does not follow every way a shell can reach
a file, so pair an origin rule with one that does not depend on attribution.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from agentleak import AgentLeakRunner, Trace

SAMPLE = Path(__file__).parent / "claude_code_subagent_transcript.jsonl"

ResourceOf = Callable[[str, dict[str, Any]], str]


def store_resource(pattern: str, node: str) -> ResourceOf:
    """Name ``node`` as the resource of any call that reaches the store.

    A call reaches the store when its input matches ``pattern``, or when it
    mentions a file the agent wrote earlier whose content matched it.
    """
    store = re.compile(pattern, re.IGNORECASE)
    scripts: set[str] = set()

    def resource_of(tool_name: str, tool_input: dict[str, Any]) -> str:
        text = json.dumps(tool_input, ensure_ascii=False)
        if store.search(text):
            path = str(tool_input.get("file_path") or "")
            if path:
                scripts.add(PureWindowsPath(path).name or PurePosixPath(path).name)
            return node
        if any(name in text for name in scripts):
            return node
        return tool_name

    return resource_of


def trace_from_transcript(
    path: Path,
    resource_of: ResourceOf | None = None,
    report_tools: frozenset[str] = frozenset(),
) -> Trace:
    """Build the trace. ``report_tools`` names any tool whose call *is* the report.

    The report is normally the sub-agent's last text; name a tool here if your
    setup hands it back through a tool call instead.
    """
    resource_of = resource_of or (lambda tool_name, _input: tool_name)
    trace = Trace(run_id=path.stem, agent_name="claude_code_subagent")
    resource_by_call: dict[str, str | None] = {}

    raw = path.read_text(encoding="utf-8")
    for line in raw.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("type") not in ("user", "assistant"):
            continue
        message = record.get("message") or {}
        role, content = message.get("role"), message.get("content")
        if isinstance(content, str):
            source, target = (
                ("main_agent", "subagent") if role == "user" else ("subagent", "main_agent")
            )
            trace.add_event("inter_agent_message", content, source=source, target=target)
            continue
        for block in content or []:
            kind = block.get("type")
            if kind == "thinking" and block.get("thinking"):
                trace.add_event("log", block["thinking"], source="subagent", target="reasoning")
            elif kind == "text" and block.get("text"):
                trace.add_event(
                    "inter_agent_message", block["text"], source="subagent", target="main_agent"
                )
            elif kind == "tool_use":
                name, tool_input = block.get("name", "unknown"), block.get("input") or {}
                if name in report_tools:
                    resource_by_call[block.get("id", "")] = None
                    trace.add_event(
                        "inter_agent_message", tool_input, source="subagent",
                        target="main_agent", metadata={"tool_name": name},
                    )
                    continue
                resource = resource_of(name, tool_input)
                resource_by_call[block.get("id", "")] = resource
                trace.add_event(
                    "tool_call", tool_input, source="subagent", target=resource,
                    metadata={"tool_name": name},
                )
            elif kind == "tool_result":
                resource = resource_by_call.get(block.get("tool_use_id", ""), "tool")
                if resource is None:
                    continue
                trace.add_event(
                    "tool_response", block.get("content", ""), source=resource, target="subagent"
                )

    # The file on disk is itself a place the data went: record it as one.
    trace.add_event(
        "generated_file", raw, source="subagent", target="transcript_on_disk",
        metadata={"file_name": path.name},
    )
    return trace


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else SAMPLE
    trace = trace_from_transcript(source, store_resource(r"customer_records\.csv", "direct_store"))

    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(
            json.dumps(trace.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"{len(trace.events)} events written to {sys.argv[2]}")
        return

    result = AgentLeakRunner().analyze(trace)
    print(f"\nPrivacy score: {result.privacy_score}/100  ({result.verdict})")
    for cr in result.score.channel_risks:
        print(f"  {cr.channel:<20} {cr.level:<9} {cr.finding_count} finding(s)")

    reported = [
        f for f in result.findings
        if str(f.channel) == "inter_agent_message" and f.source == "subagent"
    ]
    if not reported:
        print("\nThe sub-agent's report is clean — but the transcript on disk kept what it read.")


if __name__ == "__main__":
    main()
