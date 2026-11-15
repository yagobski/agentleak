# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""An agent fixing itself: self-test, apply next_steps[0].fix, re-test, until green.

This is the loop an autonomous agent runs, scripted so it can be checked:

1. ``agentleak selftest --cmd "<agent>" --json`` (subprocess, JSON on stdout)
2. read ``next_steps[0]``; if its ``fix`` is ``apply_defense`` with
   ``agentleak.defenses.Sanitizer``, add ``fix.channel`` to the agent's
   ``sanitize`` list and merge ``fix.settings.extra_patterns``
3. run the ``rerun`` command the document gave, until ``passed`` is true

It works on a copy of ``leaky_agent.py`` in a scratch directory, so the repo's
example stays leaky. Synthetic data only; nothing leaves the machine.

    python examples/selftest/fix_loop.py            # human transcript
    python examples/selftest/fix_loop.py --json     # one JSON line per iteration
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MAX_ITERATIONS = 10


def selftest(argv: list[str], workdir: Path) -> dict[str, Any]:
    proc = subprocess.run(argv, capture_output=True, text=True, cwd=workdir, check=False)
    if proc.returncode not in (0, 1):
        raise SystemExit(f"self-test could not run (exit {proc.returncode}): {proc.stdout[-400:]}")
    doc: dict[str, Any] = json.loads(proc.stdout)
    assert doc["exit_code"] == proc.returncode
    return doc


def apply_fix(step: dict[str, Any], config_path: Path) -> str:
    """What an agent does with one next step. Returns a one-line description."""
    fix = step.get("fix") or {}
    if fix.get("type") != "apply_defense" or fix.get("defense") != "agentleak.defenses.Sanitizer":
        return f"skipped {step['kind']}: no automatic fix"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    channel = fix["channel"]
    if channel not in config["sanitize"]:
        config["sanitize"].append(channel)
    patterns = (fix.get("settings") or {}).get("extra_patterns") or {}
    config["extra_patterns"].update(patterns)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    extra = f" + extra_patterns {sorted(patterns)}" if patterns else ""
    return f"Sanitizer on {channel}{extra}"


def run_loop(workdir: Path, *, agentleak: list[str], fail_on: str = "L3") -> list[dict[str, Any]]:
    shutil.copy(HERE / "leaky_agent.py", workdir / "leaky_agent.py")
    config_path = workdir / "agent_config.json"
    config_path.write_text(json.dumps({"sanitize": [], "extra_patterns": {}}), encoding="utf-8")
    argv = [*agentleak, "selftest", "--cmd", f"{shlex_quote(sys.executable)} leaky_agent.py",
            "--fail-on", fail_on, "--json"]
    transcript: list[dict[str, Any]] = []
    for iteration in range(1, MAX_ITERATIONS + 1):
        doc = selftest(argv, workdir)
        leaking = [c["channel"] for c in doc["channels"] if c["status"] == "leak"]
        row: dict[str, Any] = {
            "iteration": iteration,
            "passed": doc["passed"],
            "exit_code": doc["exit_code"],
            "privacy_score": doc["privacy_score"],
            "risk_index": doc["risk_index"],
            "leaking_channels": leaking,
            "findings": doc["findings_total"],
            "delta": None if doc["delta"] is None else {
                k: doc["delta"][k] for k in ("direction", "delta_score")
            } | {"fixed": len(doc["delta"]["fixed"]), "new": len(doc["delta"]["new"])},
        }
        if doc["passed"]:
            row["applied"] = None
            transcript.append(row)
            break
        row["applied"] = apply_fix(doc["next_steps"][0], config_path)
        transcript.append(row)
        # Re-run exactly what the document says (with the python we are using).
        argv = list(doc["rerun"]["argv"])
        argv[0:2] = [*agentleak, "selftest"]
    return transcript


def shlex_quote(value: str) -> str:
    import shlex

    return shlex.quote(value)


def main() -> int:
    as_json = "--json" in sys.argv
    agentleak = [sys.executable, "-m", "agentleak"]
    with tempfile.TemporaryDirectory(prefix="agentleak-fixloop-") as tmp:
        transcript = run_loop(Path(tmp), agentleak=agentleak)
    for row in transcript:
        if as_json:
            print(json.dumps(row))
            continue
        delta = row["delta"]
        moved = "" if delta is None else (
            f"  ({delta['direction']}, score {delta['delta_score']:+d}, "
            f"{delta['fixed']} fixed, {delta['new']} new)")
        state = "PASS" if row["passed"] else "FAIL"
        print(f"iteration {row['iteration']}: {state} exit={row['exit_code']} "
              f"score={row['privacy_score']} RI={row['risk_index']}{moved}")
        if row["leaking_channels"]:
            print(f"  leaking: {', '.join(row['leaking_channels'])}")
        if row["applied"]:
            print(f"  applied next_steps[0].fix: {row['applied']}")
    return 0 if transcript and transcript[-1]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
