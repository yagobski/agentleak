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
import threading
from dataclasses import dataclass, field
from typing import Any

from ..core.trace import Channel

_ALLOWED = {c.value for c in Channel}
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024
_DRAIN_SECONDS = 2.0


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
        out, err, err_total, overflow, _held = _collect(proc, payload.encode("utf-8"), timeout, run)
        run.duration_s = round(time.monotonic() - start, 3)
        run.exit_code = proc.returncode
    out_text = out[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
    err_text = err.decode("utf-8", errors="replace")
    run.stderr_bytes = err_total
    run.events, run.ignored_lines, run.rejected_events = parse_agent_output(out_text)
    if overflow:
        run.error = (f"stopped: the agent wrote more than {MAX_OUTPUT_BYTES} bytes to stdout "
                     "(only the part before the limit was scored)")
    elif run.timed_out:
        run.error = f"timed out after {timeout:g}s"
    elif run.exit_code != 0:
        run.error = f"exited with code {run.exit_code}"
    if run.error and err_text.strip():
        run.stderr_tail = _redacted_tail(err_text)
    return run


def _pump(stream: Any, keep: int, *, tail: bool, sink: dict[str, Any],
          overflow: threading.Event | None) -> None:
    """Read ``stream`` to EOF keeping at most ``keep`` bytes (head, or tail)."""
    # The sink is filled as data arrives: a reader still blocked on a pipe
    # that a stray process holds open must not lose what was already read.
    buf: bytearray = sink["data"]
    fd = stream.fileno()
    while True:
        try:
            chunk = os.read(fd, 65536)
        except OSError:
            break
        if not chunk:
            break
        with sink["lock"]:
            sink["total"] += len(chunk)
            if tail:
                buf += chunk
                if len(buf) > keep:
                    del buf[: len(buf) - keep]
            elif len(buf) < keep:
                buf += chunk[: keep - len(buf)]
        if overflow is not None and sink["total"] > keep:
            overflow.set()


def _feed(stream: Any, data: bytes) -> None:
    try:
        stream.write(data)
        stream.close()
    except (BrokenPipeError, OSError, ValueError):
        pass  # the agent need not read stdin (it has $AGENTLEAK_SCENARIO_FILE)


def _collect(
    proc: subprocess.Popen[bytes], payload: bytes, timeout: float, run: AgentRun
) -> tuple[bytes, bytes, int, bool, bool]:
    """Feed stdin, read stdout/stderr with hard caps, enforce the timeout.

    ``communicate()`` held everything the agent printed in memory (a child
    writing gigabytes exhausted it) and, after a timeout, waited without a
    limit for EOF, which never comes when a grandchild that left the process
    group (``setsid``) still holds the pipe. Here memory is bounded, output
    past the limit stops the run, and nothing waits forever.
    """
    import time

    out_sink: dict[str, Any] = {"data": bytearray(), "total": 0, "lock": threading.Lock()}
    err_sink: dict[str, Any] = {"data": bytearray(), "total": 0, "lock": threading.Lock()}
    overflow = threading.Event()
    readers = [
        threading.Thread(target=_pump, args=(proc.stdout, MAX_OUTPUT_BYTES),
                         kwargs={"tail": False, "sink": out_sink, "overflow": overflow}, daemon=True),
        threading.Thread(target=_pump, args=(proc.stderr, MAX_STDERR_BYTES),
                         kwargs={"tail": True, "sink": err_sink, "overflow": None}, daemon=True),
    ]
    for t in readers:
        t.start()
    threading.Thread(target=_feed, args=(proc.stdin, payload), daemon=True).start()
    deadline = time.monotonic() + timeout
    overflowed = False
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            run.timed_out = True
            break
        try:
            proc.wait(timeout=min(0.05, remaining))
            break
        except subprocess.TimeoutExpired:
            if overflow.is_set():
                overflowed = True
                break
    if run.timed_out or overflowed:
        _kill_group(proc)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    for t in readers:
        t.join(timeout=_DRAIN_SECONDS)
    held = any(t.is_alive() for t in readers)
    if held:
        # The agent exited but something it started still holds the pipe:
        # stop what is left of its process group, then give up on the pipe.
        _kill_group(proc)
        for t in readers:
            t.join(timeout=_DRAIN_SECONDS)
        held = any(t.is_alive() for t in readers)
    with out_sink["lock"], err_sink["lock"]:
        out, err = bytes(out_sink["data"]), bytes(err_sink["data"])
        err_total = int(err_sink["total"])
    return out, err, err_total, overflowed, held


def _kill_group(proc: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (AttributeError, ProcessLookupError, PermissionError, OSError):
        proc.kill()  # Windows has no process groups here; kill the child itself


__all__ = ["AgentRun", "MAX_OUTPUT_BYTES", "parse_agent_output", "run_scenario", "split_command"]
