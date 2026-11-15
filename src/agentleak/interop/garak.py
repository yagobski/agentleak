# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""garak ``report.jsonl`` -> AgentLeak traces.

Verified against garak 0.17.1: a real offline run (``--target_type function``
pointing at a local stub, probes ``test.Test`` and ``dan.Dan_11_0``). See
``tests/fixtures/interop/README.md``.

A report is JSON lines with an ``entry_type``. Attempt records appear twice,
once when the prompt is sent (``status`` 1) and once after detection
(``status`` 2); the last record for each ``uuid`` is kept. One trace per attempt:

* ``prompt.turns`` with role ``user`` -> user_input; a ``system`` turn ->
  user_input (source ``system``); an ``assistant`` turn inside the prompt is
  history the probe wrote, so it is input too -> user_input (source
  ``prompt_history``)
* each entry of ``outputs`` (one per generation) -> final_output

garak drives a model or an endpoint from the outside: it sees the prompt and
the text that came back, nothing in between. An imported garak trace has only
user_input and final_output, and its report says the other channels were not
observed. Detector scores, probe, goal and intent ride along as labels.
"""

from __future__ import annotations

from typing import Any

from ..core.trace import Trace
from .base import (
    MAX_TRACES,
    ImportedTrace,
    ImportResult,
    InteropError,
    observation,
    safe_id,
    stamp,
)
from .source import Source

TOOL = "garak"
OBSERVABLE = ["user_input", "final_output"]
_NOTE = (
    "garak records only the prompt it sent and the text the model returned. Tool calls, tool "
    "results, memory, logs, inter-agent messages and files were not observed, so they were not "
    "audited: no finding on them is not evidence that they are clean."
)
_ENTRY_TYPES = {"init", "attempt", "start_run setup", "eval", "completion", "digest"}


def sniff(src: Source) -> tuple[bool, str]:
    rows = src.value
    if src.kind != "jsonl" or not isinstance(rows, list):
        return False, "not JSON lines"
    kinds = {r.get("entry_type") for r in rows if isinstance(r, dict)}
    if "attempt" in kinds and kinds & {"init", "start_run setup"}:
        return True, "JSON lines with garak 'entry_type' records ('init'/'start_run setup' and 'attempt')"
    if kinds & _ENTRY_TYPES:
        return False, "garak-like 'entry_type' records but no 'attempt' with an 'init' record"
    return False, "no 'entry_type' records"


def _text(value: Any) -> str | None:
    """Text of a garak Message ({"text": ...}) or a plain string."""
    if isinstance(value, dict):
        value = value.get("text")
    return value if isinstance(value, str) else None


def trace_from_attempt(attempt: dict[str, Any], *, run_id: str) -> tuple[Trace, int]:
    """One attempt -> trace. Returns the trace and how many outputs were empty."""
    trace = Trace(run_id=run_id, agent_name="garak_target")
    prompt = attempt.get("prompt")
    if not isinstance(prompt, dict) or not isinstance(prompt.get("turns"), list):
        raise InteropError(
            f"attempt {attempt.get('uuid')}: 'prompt' is not a garak Conversation "
            "({'turns': [...]}). Reports from garak before Conversation prompts are not supported."
        )
    for turn in prompt["turns"]:
        if not isinstance(turn, dict):
            continue
        text = _text(turn.get("content"))
        if not text:
            continue
        role = turn.get("role")
        source = {"system": "system", "assistant": "prompt_history"}.get(str(role), "garak")
        trace.add_event("user_input", text, source=source, target="target",
                        metadata={"role": role})
    empty = 0
    for index, output in enumerate(attempt.get("outputs") or []):
        text = _text(output)
        if text is None or not text.strip():
            empty += 1
            continue
        trace.add_event("final_output", text, source="target", target="garak",
                        metadata={"generation": index})
    return trace, empty


def convert(src: Source, reason: str) -> ImportResult:
    rows = [r for r in src.value if isinstance(r, dict)]
    version = next((r.get("garak_version") for r in rows if r.get("entry_type") == "init"), None)
    if version is None:
        version = next((r.get("_config.version") for r in rows
                        if r.get("entry_type") == "start_run setup"), None)
    run_uuid = next((r.get("run") for r in rows if r.get("entry_type") == "init"), None)
    notes: list[str] = []
    result = ImportResult(
        tool=TOOL, tool_version=version, source_file=src.name, source_sha256=src.sha256,
        detected_because=reason, verification="real run (garak 0.17.1)",
        observable_channels=OBSERVABLE, notes=notes,
    )
    latest: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        if row.get("entry_type") != "attempt":
            continue
        key = str(row.get("uuid") or f"row{len(order)}")
        if key not in latest:
            order.append(key)
            latest[key] = row
        elif int(row.get("status") or 0) >= int(latest[key].get("status") or 0):
            latest[key] = row
    obs = observation(TOOL, OBSERVABLE, _NOTE)
    empty_total = 0
    unevaluated = 0
    for key in order[:MAX_TRACES]:
        attempt = latest[key]
        probe = str(attempt.get("probe_classname") or "probe")
        run_id = safe_id(f"garak_{probe}_{attempt.get('seq', 0)}_{key[:8]}", "garak")
        trace, empty = trace_from_attempt(attempt, run_id=run_id)
        empty_total += empty
        if int(attempt.get("status") or 0) < 2:
            unevaluated += 1
        if not trace.events:
            result.skipped += 1
            continue
        stamp(trace, tool=TOOL, tool_version=version, source_file=src.name,
              source_sha256=src.sha256, record_id=key, observation_=obs,
              labels={k: v for k, v in {
                  "run": run_uuid, "probe": probe, "seq": attempt.get("seq"),
                  "goal": attempt.get("goal"), "intent": attempt.get("intent"),
                  "status": attempt.get("status"),
                  "detector_results": attempt.get("detector_results") or None,
              }.items() if v not in (None, "")})
        result.traces.append(ImportedTrace(record_id=key, trace=trace))
    if len(order) > MAX_TRACES:
        notes.append(f"stopped after {MAX_TRACES} attempts")
    if empty_total:
        notes.append(f"{empty_total} generation(s) returned no text and were not imported")
    if unevaluated:
        notes.append(f"{unevaluated} attempt(s) never reached detection (status < 2); their "
                     "prompt and outputs were imported anyway")
    if result.skipped:
        notes.append(f"{result.skipped} attempt(s) had neither prompt text nor output")
    return result
