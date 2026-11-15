# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""``agentleak selftest`` hardening regressions: child process limits, history.

The agents here are tiny synthetic Python scripts written to a temp dir.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
from pathlib import Path

import pytest

from agentleak.selftest.protocol import MAX_OUTPUT_BYTES, run_scenario

_ISSUED = {"protocol": "agentleak.selftest.v1", "scenario": {"id": "s", "instance_id": "i"}}
_EVENT = json.dumps({"channel": "final_output", "content": "done"})


def _script(tmp_path: Path, body: str) -> list[str]:
    path = tmp_path / "agent.py"
    path.write_text(body, encoding="utf-8")
    return [sys.executable, str(path)]


def _run_bounded(cmd: list[str], *, timeout: float, wall: float):  # noqa: ANN202
    box: dict[str, object] = {}
    t = threading.Thread(target=lambda: box.setdefault("run", run_scenario(cmd, _ISSUED, timeout=timeout)),
                         daemon=True)
    started = time.monotonic()
    t.start()
    t.join(wall)
    return box.get("run"), time.monotonic() - started


@pytest.mark.skipif(os.name == "nt", reason="POSIX sessions")
def test_a_grandchild_holding_stdout_does_not_hang_the_selftest(tmp_path: Path) -> None:
    pidfile = tmp_path / "grandchild.pid"
    cmd = _script(tmp_path, f"""
import subprocess, sys
p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"], start_new_session=True)
open({str(pidfile)!r}, "w").write(str(p.pid))
print({_EVENT!r}, flush=True)
""")
    try:
        run, elapsed = _run_bounded(cmd, timeout=3, wall=30)
        assert run is not None, "run_scenario did not return: it waits for a pipe it cannot close"
        assert elapsed < 30
        assert run.events and run.events[0]["channel"] == "final_output"
    finally:
        if pidfile.exists():
            try:
                os.kill(int(pidfile.read_text()), signal.SIGKILL)
            except (ProcessLookupError, ValueError):
                pass


def test_stdout_over_the_limit_stops_the_run_early(tmp_path: Path) -> None:
    cmd = _script(tmp_path, f"""
import sys, time
print({_EVENT!r}, flush=True)
chunk = "x" * (1 << 20)
for _ in range({MAX_OUTPUT_BYTES // (1 << 20) + 4}):
    sys.stdout.write(chunk)
sys.stdout.flush()
time.sleep(60)
""")
    run, elapsed = _run_bounded(cmd, timeout=40, wall=60)
    assert run is not None
    assert elapsed < 30, "an agent flooding stdout ran until the timeout"
    assert run.error and "more than" in run.error
    assert not run.timed_out
