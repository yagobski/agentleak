#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Claude Code Stop hook: self-test the session transcript before Claude stops.

Install: copy to ``.claude/hooks/agentleak_stop_hook.py`` in your project and
add to ``.claude/settings.json``::

    {
      "hooks": {
        "Stop": [
          {"hooks": [{"type": "command",
                      "command": "python3 \\"$CLAUDE_PROJECT_DIR\\"/.claude/hooks/agentleak_stop_hook.py"}]}
        ]
      }
    }

What it does, per the Claude Code hooks reference (Stop input: ``transcript_path``,
``cwd``, ``stop_hook_active``; output ``{"decision": "block", "reason": ...}``):

* runs ``agentleak selftest --trace <transcript_path> --trace-format claude_code
  --fail-on L4 --json`` locally (no network);
* if an L4 finding (credential, national ID, card, health data) reached a
  disclosure channel — an answer, a file Claude wrote, a command it ran —
  it blocks the stop and tells Claude what leaked (redacted) and how to fix it;
* if ``stop_hook_active`` is already true it does not block again, so it can
  never trap the session in a loop; it still prints the result to stderr.

The transcript is data. Nothing in it is executed or followed by this hook.
Set ``AGENTLEAK_HOOK_FAIL_ON=L3`` for a stricter gate.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # not our input; never block on a hook malfunction
    transcript = event.get("transcript_path") or ""
    transcript = os.path.expanduser(transcript)
    if not transcript or not os.path.isfile(transcript):
        return 0
    agentleak = shutil.which("agentleak")
    base = [agentleak] if agentleak else [sys.executable, "-m", "agentleak"]
    cwd = event.get("cwd") or os.getcwd()
    fail_on = os.environ.get("AGENTLEAK_HOOK_FAIL_ON", "L4")
    proc = subprocess.run(
        [*base, "selftest", "--trace", transcript, "--trace-format", "claude_code",
         "--fail-on", fail_on, "--json", "--state-dir", os.path.join(cwd, ".agentleak")],
        capture_output=True, text=True, cwd=cwd, check=False, timeout=120,
    )
    if proc.returncode not in (0, 1):
        print(f"agentleak self-test could not run (exit {proc.returncode})", file=sys.stderr)
        return 0
    doc = json.loads(proc.stdout)
    if doc["passed"]:
        return 0
    leaks = [s for s in doc["next_steps"] if s["kind"] in ("runtime_leak", "canary_leak")]
    lines = [f"AgentLeak self-test: {doc['summary']}"]
    for step in leaks[:5]:
        ev = step.get("evidence") or [{}]
        lines.append(f"- {step['channel']}: {', '.join(step['data_types'])} "
                     f"(e.g. {ev[0].get('redacted_value', '?')}). {step['action']}")
    lines.append("Remove or rotate the exposed values, avoid repeating them in answers, files "
                 "or commands, then finish. Details: agentleak selftest --status")
    reason = "\n".join(lines)
    if event.get("stop_hook_active"):
        print(reason, file=sys.stderr)
        return 0
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
