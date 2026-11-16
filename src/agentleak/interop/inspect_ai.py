# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Inspect AI eval logs (``.eval`` and ``.json``) -> AgentLeak traces.

Verified against Inspect AI 0.3.290: a real offline eval (``mockllm/model``
with scripted tool calls, a tool error-free run, a reasoning part) written in
both log formats. See ``tests/fixtures/interop/README.md``.

* ``.eval`` is a zip archive: ``header.json`` (the eval spec, with
  ``eval.packages.inspect_ai``) and one ``samples/<id>_epoch_<n>.json`` per
  sample. Members are read in memory, by name, within size limits; nothing is
  extracted. Inspect 0.3.290 compresses members with zstd, which Python reads
  natively from 3.14, or with the optional ``zstandard`` package.
* ``.json`` is the same log in one document, samples inline.

One trace per sample (and epoch), from its ``messages``:

=============================  =========================================
message                        channel
=============================  =========================================
``system``                     user_input (source ``system``)
``user``                       user_input
``assistant`` ``tool_calls``   tool_call (target: the function), except
                               ``transfer_to_<agent>``: inter_agent_message
``assistant`` reasoning part   log (not when the reasoning is redacted)
``assistant`` text             inter_agent_message; the last one final_output
``assistant`` tool_use part    tool_call + tool_response (server-side tools)
``tool``                       tool_response (the error message included)
=============================  =========================================

Not imported: the sample ``store`` and the ``events`` log (sandbox commands,
store changes, model calls). Inspect runs the tools itself, so tool traffic is
observed; shared memory and generated files are not.
"""

from __future__ import annotations

import re
from typing import Any

from ..core.trace import Trace
from .base import (
    MAX_TRACES,
    ImportedTrace,
    ImportResult,
    InteropError,
    obj,
    observation,
    safe_id,
    stamp,
)
from .source import Source

TOOL = "inspect_ai"
OBSERVABLE = ["user_input", "tool_call", "tool_response", "inter_agent_message", "log", "final_output"]
_NOTE = (
    "Inspect AI runs the agent's tools, so tool calls and tool results were observed. The sample "
    "store, sandbox activity and generated files are not part of the messages and were not "
    "audited."
)
_ATTACHMENT = re.compile(r"^attachment://([0-9a-f]{8,64})$")


# ----------------------------------------------------------------------
# detection
# ----------------------------------------------------------------------
def sniff(src: Source) -> tuple[bool, str]:
    if src.kind == "zip":
        assert src.archive is not None
        names = set(src.archive.names)
        if "header.json" in names or "_journal/start.json" in names:
            return True, "a zip archive with Inspect's 'header.json' / '_journal/start.json' members"
        return False, "a zip archive without 'header.json' or '_journal/start.json'"
    doc = src.value
    if src.kind == "json" and isinstance(doc, dict):
        spec = doc.get("eval")
        if isinstance(spec, dict) and "task" in spec and isinstance(doc.get("version"), int):
            return True, "a JSON object with 'version' and an 'eval' spec naming a 'task'"
        return False, "no 'eval' spec with a 'task'"
    return False, "neither an .eval archive nor a JSON object"


# ----------------------------------------------------------------------
# conversion
# ----------------------------------------------------------------------
def _resolve(value: Any, attachments: dict[str, Any]) -> Any:
    """Inspect condenses repeated content into ``attachment://<hash>`` references
    to the sample's own ``attachments``. Only that in-file table is consulted."""
    if isinstance(value, str):
        match = _ATTACHMENT.match(value)
        if match and isinstance(attachments.get(match[1]), str):
            return attachments[match[1]]
    return value


def _parts(content: Any, attachments: dict[str, Any]) -> list[dict[str, Any]]:
    content = _resolve(content, attachments)
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [p for p in content if isinstance(p, dict)]
    return []


def _text(parts: list[dict[str, Any]], attachments: dict[str, Any]) -> str:
    texts = [str(_resolve(p.get("text"), attachments) or "") for p in parts if p.get("type") == "text"]
    return "\n".join(t for t in texts if t.strip())


def trace_from_messages(messages: list[Any], *, run_id: str,
                        attachments: dict[str, Any] | None = None) -> tuple[Trace, int]:
    """Inspect ``ChatMessage`` dicts -> trace. Returns the trace and how many
    non-text parts (images, audio, documents) were skipped."""
    attachments = attachments or {}
    trace = Trace(run_id=run_id, agent_name="inspect_agent")
    names: dict[str, str] = {}
    agent = "agent"
    skipped = 0
    msgs = [m for m in messages if isinstance(m, dict)]
    last_text = max((i for i, m in enumerate(msgs) if m.get("role") == "assistant"
                     and _text(_parts(m.get("content"), attachments), attachments)), default=-1)
    for i, m in enumerate(msgs):
        role = m.get("role")
        parts = _parts(m.get("content"), attachments)
        skipped += sum(1 for p in parts if p.get("type") not in ("text", "reasoning", "tool_use"))
        text = _text(parts, attachments)
        if role in ("system", "user"):
            if text:
                trace.add_event("user_input", text, source=str(role), target=agent,
                                metadata={"message_id": m.get("id")})
        elif role == "tool":
            call_id = str(m.get("tool_call_id") or "")
            tool = str(m.get("function") or names.get(call_id) or "tool")
            error = m.get("error") if isinstance(m.get("error"), dict) else None
            body = text
            if error and error.get("message"):
                body = (body + "\n" if body else "") + f"error: {error['message']}"
            trace.add_event("tool_response", body, source=tool, target=agent,
                            metadata={"tool_name": tool, "tool_call_id": call_id,
                                      "message_id": m.get("id")})
        elif role == "assistant":
            for part in parts:
                if part.get("type") == "reasoning" and not part.get("redacted"):
                    thought = str(_resolve(part.get("reasoning"), attachments) or part.get("summary") or "")
                    if thought.strip():
                        trace.add_event("log", thought, source=agent, target="reasoning",
                                        metadata={"message_id": m.get("id")})
                elif part.get("type") == "tool_use":
                    tool = str(part.get("name") or part.get("tool_type") or "tool")
                    trace.add_event("tool_call", str(_resolve(part.get("arguments"), attachments) or ""),
                                    source=agent, target=tool,
                                    metadata={"tool_name": tool, "tool_type": part.get("tool_type"),
                                              "tool_call_id": part.get("id")})
                    result = _resolve(part.get("result"), attachments)
                    if result not in (None, ""):
                        trace.add_event("tool_response", str(result), source=tool, target=agent,
                                        metadata={"tool_name": tool, "tool_call_id": part.get("id")})
            for call in m.get("tool_calls") or []:
                if not isinstance(call, dict):
                    continue
                fn = str(call.get("function") or "tool")
                call_id = str(call.get("id") or "")
                names[call_id] = fn
                args = _resolve(call.get("arguments"), attachments)
                args = args if isinstance(args, (str, dict, list)) else str(args)
                if fn.startswith("transfer_to_"):
                    peer = fn.removeprefix("transfer_to_")
                    trace.add_event("inter_agent_message", args or "", source=agent, target=peer,
                                    metadata={"handoff": True, "tool_name": fn, "tool_call_id": call_id})
                    agent = peer
                else:
                    trace.add_event("tool_call", args if args is not None else "", source=agent,
                                    target=fn, metadata={"tool_name": fn, "tool_call_id": call_id})
            if text:
                final = i == last_text
                trace.add_event("final_output" if final else "inter_agent_message", text,
                                source=agent, target="user" if final else "agent",
                                metadata={"message_id": m.get("id")})
    return trace, skipped


def _scores(sample: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, score in (sample.get("scores") or {}).items():
        if isinstance(score, dict) and isinstance(score.get("value"), (str, int, float, bool)):
            out[str(name)] = score["value"]
    return out


def _samples_from_archive(src: Source, notes: list[str]) -> tuple[dict[str, Any], list[Any]]:
    archive = src.archive
    assert archive is not None
    names = set(archive.names)
    if "header.json" in names:
        header = archive.read_json("header.json")
    elif "_journal/start.json" in names:
        header = archive.read_json("_journal/start.json")
        notes.append("the log has no header.json: the eval had not finished when it was read")
    else:  # pragma: no cover - sniff() refuses this
        raise InteropError(f"{src.name} has no Inspect header")
    members = sorted(n for n in archive.names if n.startswith("samples/") and n.endswith(".json"))
    samples = []
    for name in members[:MAX_TRACES]:
        samples.append(archive.read_json(name))
    if len(members) > MAX_TRACES:
        notes.append(f"stopped after {MAX_TRACES} samples")
    return obj(header), samples


def convert(src: Source, reason: str) -> ImportResult:
    notes: list[str] = []
    if src.kind == "zip":
        header, samples = _samples_from_archive(src, notes)
    else:
        header = src.value
        samples = list(header.get("samples") or [])
        if not samples:
            notes.append("the JSON log has no 'samples' (it was written with samples excluded); "
                         "nothing to import")
    spec = obj(header.get("eval"))
    packages = obj(spec.get("packages"))
    version = packages.get("inspect_ai")
    if header.get("status") not in (None, "success"):
        notes.append(f"the eval status is {header.get('status')!r}, not 'success'")
    result = ImportResult(
        tool=TOOL, tool_version=version, source_file=src.name, source_sha256=src.sha256,
        detected_because=reason, verification="real run (Inspect AI 0.3.290, .eval and .json)",
        observable_channels=OBSERVABLE, notes=notes,
    )
    task = str(spec.get("task") or "inspect")
    obs = observation(TOOL, OBSERVABLE, _NOTE)
    skipped_parts = 0
    for index, sample in enumerate(samples):
        if not isinstance(sample, dict) or not isinstance(sample.get("messages"), list):
            result.skipped += 1
            continue
        sid, epoch = sample.get("id", index), sample.get("epoch", 1)
        record_id = f"{sid}_epoch_{epoch}"
        attachments = obj(sample.get("attachments"))
        trace, skipped = trace_from_messages(
            sample["messages"], run_id=safe_id(f"{task}_{record_id}", f"inspect_{index}"),
            attachments=attachments)
        skipped_parts += skipped
        if not trace.events:
            result.skipped += 1
            continue
        if sample.get("error"):
            notes.append(f"sample {record_id} ended with an error; its messages up to the error "
                         "were imported")
        stamp(trace, tool=TOOL, tool_version=version, source_file=src.name,
              source_sha256=src.sha256, record_id=record_id, observation_=obs,
              labels={k: v for k, v in {
                  "task": spec.get("task"), "model": spec.get("model"), "sample_id": sid,
                  "epoch": epoch, "uuid": sample.get("uuid"), "scores": _scores(sample) or None,
              }.items() if v not in (None, "")})
        result.traces.append(ImportedTrace(record_id=record_id, trace=trace))
    if skipped_parts:
        notes.append(f"{skipped_parts} non-text content part(s) (images, audio, documents) were "
                     "not scanned")
    if result.skipped:
        notes.append(f"{result.skipped} sample(s) had no readable messages")
    return result


__all__ = ["convert", "sniff", "trace_from_messages"]
