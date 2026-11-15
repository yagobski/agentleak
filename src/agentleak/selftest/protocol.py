# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Run the user's own agent command against one scenario, collect its events.

The protocol (``agentleak.selftest.v1``), from the agent's side:

1. The command is started once per scenario, in its own process.
2. Its **stdin** receives one JSON document: ``{"protocol", "scenario",
   "reply_with"}`` (see :func:`agentleak.selftest.battery.issue`). The same
   document is also written to a temporary file named by
   ``$AGENTLEAK_SCENARIO_FILE`` for agents that do not read stdin.
   ``$AGENTLEAK_SELFTEST=1`` and ``$AGENTLEAK_SCENARIO_ID`` are set too.
3. On **stdout** the agent writes one JSON object per line, one per action:
   ``{"channel": "log", "content": "...", "target": "debug.log"}``. A single
   ``{"events": [...]}`` document is accepted as well. Lines that are not JSON
   objects are ignored and counted.
4. Exit code 0 means the run finished. Anything else, or a timeout, makes the
   scenario ``incomplete``; the events received before that are still scored.

Safety rules this module enforces:

* The command is split into an argv list with :func:`shlex.split` and executed
  without a shell, so nothing in it is interpreted twice. ``shell=True`` is
  used only when the caller passes ``use_shell`` (CLI: ``--shell``).
* Each scenario runs in a fresh process with a per-scenario timeout; on
  timeout the whole process group is killed.
* The agent's stderr is never copied into the result. Only its size and, on
  failure, a short redacted tail are reported.
* Nothing the agent prints is executed or followed. It is data.
"""

from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Any

from ..core.trace import Channel

_ALLOWED = {c.value for c in Channel}
MAX_OUTPUT_BYTES = 8 * 1024 * 1024


@dataclass
class AgentRun:
    """What one scenario run of the agent produced."""

    events: list[dict[str, Any]] = field(default_factory=list)
    exit_code: int | None = None
    timed_out: bool = False
    ignored_lines: int = 0
    rejected_events: int = 0
    stderr_bytes: int = 0
    stderr_tail: str = ""
    error: str | None = None
    duration_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None and not self.timed_out and self.exit_code == 0


def split_command(command: str | list[str]) -> list[str]:
    """argv for ``command``; a list is used as is."""
    if isinstance(command, list):
        return [str(a) for a in command]
    argv = shlex.split(command)
    if not argv:
        raise ValueError("empty agent command")
    return argv


def parse_agent_output(text: str) -> tuple[list[dict[str, Any]], int, int]:
    """``(events, ignored_lines, rejected_events)`` from the agent's stdout."""
    stripped = text.strip()
    if stripped.startswith("{") and '"events"' in stripped[:200]:
        try:
            doc = json.loads(stripped)
        except json.JSONDecodeError:
            doc = None
        if isinstance(doc, dict) and isinstance(doc.get("events"), list):
            good = [e for e in doc["events"] if _valid(e)]
            return good, 0, len(doc["events"]) - len(good)
    events: list[dict[str, Any]] = []
    ignored = rejected = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            ignored += 1
            continue
        if not isinstance(obj, dict):
            ignored += 1
        elif _valid(obj):
            events.append(obj)
        else:
            rejected += 1
    return events, ignored, rejected


def _valid(event: Any) -> bool:
    return isinstance(event, dict) and event.get("channel") in _ALLOWED and "content" in event


def _redacted_tail(text: str, limit: int = 400) -> str:
    from ..defenses import Sanitizer

    tail = text[-limit:]
    try:
        return Sanitizer().sanitize(tail)
    except Exception:  # noqa: BLE001 - never let reporting fail the run
        return "[stderr withheld]"


def run_scenario(
    command: str | list[str],
    issued_public: dict[str, Any],
    *,
    timeout: float = 60.0,
    use_shell: bool = False,
    cwd: str | None = None,
) -> AgentRun:
    """Start the agent once on one scenario and collect what it reports."""
    import time

    payload = json.dumps(issued_public, ensure_ascii=False)
    scenario = issued_public.get("scenario", {})
    run = AgentRun()
    with tempfile.TemporaryDirectory(prefix="agentleak-selftest-") as tmp:
        scenario_file = os.path.join(tmp, "scenario.json")
        with open(scenario_file, "w", encoding="utf-8") as fh:
            fh.write(payload)
        env = dict(os.environ)
        env.update({
            "AGENTLEAK_SELFTEST": "1",
            "AGENTLEAK_SELFTEST_PROTOCOL": "agentleak.selftest.v1",
            "AGENTLEAK_SCENARIO_FILE": scenario_file,
            "AGENTLEAK_SCENARIO_ID": str(scenario.get("id", "")),
            "AGENTLEAK_SCENARIO_INSTANCE": str(scenario.get("instance_id", "")),
        })
        # Never let a nested `agentleak selftest` inside the agent write JSON
        # into the stream we are parsing by surprise.
        env.pop("AGENTLEAK_JSON", None)
        try:
            argv: str | list[str] = command if use_shell and isinstance(command, str) else split_command(command)
        except ValueError as exc:
            run.error = f"cannot parse the agent command: {exc}"
            return run
        start = time.monotonic()
        try:
            proc = subprocess.Popen(  # noqa: S603 - argv list, no shell unless asked
                argv,
                shell=use_shell,  # noqa: S602 - explicit opt-in only (--shell)
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                env=env,
                start_new_session=True,
            )
        except (FileNotFoundError, PermissionError, OSError) as exc:
            run.error = f"cannot start the agent command: {exc}"
            return run
        try:
            out, err = proc.communicate(payload.encode("utf-8"), timeout=timeout)
        except subprocess.TimeoutExpired:
            run.timed_out = True
            _kill_group(proc)
            out, err = proc.communicate()
        run.duration_s = round(time.monotonic() - start, 3)
        run.exit_code = proc.returncode
    out_text = out[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
    err_text = err.decode("utf-8", errors="replace")
    run.stderr_bytes = len(err)
    run.events, run.ignored_lines, run.rejected_events = parse_agent_output(out_text)
    if run.timed_out:
        run.error = f"timed out after {timeout:g}s"
    elif run.exit_code != 0:
        run.error = f"exited with code {run.exit_code}"
    if run.error and err_text.strip():
        run.stderr_tail = _redacted_tail(err_text)
    return run


def _kill_group(proc: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (AttributeError, ProcessLookupError, PermissionError, OSError):
        proc.kill()  # Windows has no process groups here; kill the child itself


__all__ = ["AgentRun", "MAX_OUTPUT_BYTES", "parse_agent_output", "run_scenario", "split_command"]
