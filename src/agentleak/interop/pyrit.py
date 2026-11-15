# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""PyRIT conversation JSON -> AgentLeak traces.

Verified against PyRIT 1.2.0. The documents are the ones PyRIT's own JSON
printers write (``pyrit.output``): a ``PromptSendingAttack`` was run offline
against a stub ``PromptTarget`` with an in-memory database, then serialized
with ``JsonConversationMemoryPrinter`` and
``build_scenario_conversations_document``, the functions behind
``output_conversation_async(format="json")``,
``output_scenario_conversations_async`` and the CLI's
``scenario-results --view conversations|full --format json``. The CLI itself
was not run: it reads results through a PyRIT server.

Accepted shapes:

* ``{"view": "conversations" | "full", "conversations": [{"id", "technique",
  "objective", "outcome", "conversation_id", "messages": [...]}, ...]}``
  (``full`` also carries ``overview.scenario.pyrit_version``)
* a bare conversation: ``[{"role", "is_simulated", "pieces": [...]}, ...]``

PyRIT 0.x wrote a different memory export (a flat list of message pieces);
it is not supported, because no sample could be verified.

Per message piece:

=====================================  ======================================
piece                                  channel
=====================================  ======================================
``system`` / ``developer``             user_input
``user``                               user_input (``converted_value``: what
                                       the target received after converters)
any piece with ``is_simulated: true``  user_input (history the attacker wrote,
                                       not something the target produced)
``assistant`` ``text`` / ``error``     final_output (``original_value``)
``assistant`` ``function_call``        tool_call (name and arguments parsed)
``assistant`` ``tool_call``            tool_call (server-side tool)
``assistant`` ``reasoning``            log (the reasoning summary)
``tool`` ``function_call_output``      tool_response
``*_path`` and ``url`` pieces          not read: the value is a file path or
                                       a URL, and an importer never opens one
=====================================  ======================================
"""

from __future__ import annotations

import json
from typing import Any

from ..core.trace import Trace
from .base import (
    MAX_TRACES,
    ImportedTrace,
    ImportResult,
    obj,
    observation,
    safe_id,
    stamp,
)
from .convert import maybe_json
from .source import Source

TOOL = "pyrit"
BLACK_BOX = ["user_input", "final_output"]
_NOTE_BLACK = (
    "PyRIT recorded only the prompts sent to the target and the replies it returned. Tool "
    "calls, memory, logs, inter-agent messages and files were not observed, so they were not "
    "audited: no finding on them is not evidence that they are clean."
)
_NOTE_TOOLS = (
    "The target returned tool traffic (function calls or results), which was imported. Memory, "
    "logs, inter-agent messages and files were not observed."
)
_MEDIA = {"image_path", "audio_path", "video_path", "binary_path", "url"}


def _is_message(value: Any) -> bool:
    return isinstance(value, dict) and "role" in value and isinstance(value.get("pieces"), list)


def sniff(src: Source) -> tuple[bool, str]:
    doc = src.value
    if src.kind != "json":
        return False, "not a JSON document"
    if isinstance(doc, dict) and doc.get("view") in ("conversations", "full") \
            and isinstance(doc.get("conversations"), list):
        return True, f"a PyRIT scenario document (view {doc['view']!r}) with a 'conversations' list"
    if isinstance(doc, list) and doc and all(_is_message(m) for m in doc):
        return True, "a list of PyRIT messages ('role', 'is_simulated', 'pieces')"
    return False, "no 'view: conversations|full' document and not a list of PyRIT messages"


def trace_from_messages(messages: list[Any], *, run_id: str) -> tuple[Trace, list[str]]:
    """PyRIT JSON messages -> trace. Returns the trace and the piece kinds skipped."""
    trace = Trace(run_id=run_id, agent_name="pyrit_target")
    names: dict[str, str] = {}
    skipped: list[str] = []
    for m in messages:
        if not _is_message(m):
            continue
        role = str(m.get("role") or "")
        simulated = bool(m.get("is_simulated"))
        for piece in m["pieces"]:
            if not isinstance(piece, dict):
                continue
            dtype = str(piece.get("data_type") or "text")
            if dtype in _MEDIA:
                skipped.append(dtype)
                continue
            meta: dict[str, Any] = {"role": role, "data_type": dtype}
            if piece.get("response_error") not in (None, "none"):
                meta["response_error"] = piece["response_error"]
            if role in ("system", "developer", "user") or simulated:
                value = piece.get("converted_value", piece.get("original_value"))
                if dtype == "reasoning":
                    value = piece.get("reasoning_summary")
                if value in (None, ""):
                    continue
                if piece.get("converted_value") not in (None, piece.get("original_value")):
                    meta["converted"] = True
                if simulated:
                    meta["simulated"] = True
                trace.add_event("user_input", str(value),
                                source="simulated_history" if simulated else role,
                                target="target", metadata=meta)
                continue
            if dtype == "reasoning":
                summary = piece.get("reasoning_summary")
                if summary:
                    trace.add_event("log", str(summary), source="target", target="reasoning",
                                    metadata=meta)
                continue
            raw = piece.get("original_value")
            if raw in (None, ""):
                raw = piece.get("partial_content")
            if raw in (None, ""):
                continue
            if role == "tool" or dtype == "function_call_output":
                payload = maybe_json(raw)
                output = payload.get("output", raw) if isinstance(payload, dict) else raw
                call_id = str(payload.get("call_id") or "") if isinstance(payload, dict) else ""
                tool = names.get(call_id, "tool")
                trace.add_event("tool_response", output if isinstance(output, (str, dict, list))
                                else json.dumps(output), source=tool, target="target",
                                metadata={**meta, "tool_name": tool, "call_id": call_id})
            elif dtype == "function_call":
                payload = maybe_json(raw)
                fn = payload.get("function") if isinstance(payload, dict) else None
                name = str((fn or {}).get("name") or (payload.get("name") if isinstance(payload, dict)
                                                       else None) or "tool")
                args = (fn or {}).get("arguments") if fn else (
                    payload.get("arguments") if isinstance(payload, dict) else raw)
                call_id = str((payload.get("call_id") or payload.get("id") or "")
                              if isinstance(payload, dict) else "")
                names[call_id] = name
                trace.add_event("tool_call", str(args if args is not None else ""), source="target",
                                target=name, metadata={**meta, "tool_name": name, "call_id": call_id})
            elif dtype == "tool_call":
                payload = maybe_json(raw)
                name = str(payload.get("type") or "tool") if isinstance(payload, dict) else "tool"
                trace.add_event("tool_call", payload if isinstance(payload, (dict, list)) else str(raw),
                                source="target", target=name, metadata={**meta, "tool_name": name})
            else:
                trace.add_event("final_output", str(raw), source="target", target="user",
                                metadata=meta)
    return trace, skipped


def convert(src: Source, reason: str) -> ImportResult:
    doc = src.value
    notes: list[str] = []
    version = None
    if isinstance(doc, dict):
        overview = obj(doc.get("overview"))
        scenario = obj(overview.get("scenario"))
        version = scenario.get("pyrit_version")
        conversations = [c for c in doc["conversations"] if isinstance(c, dict)]
        scenario_id = safe_id(doc.get("scenario_result_id"), "pyrit")
    else:
        conversations = [{"id": "conversation", "messages": doc}]
        scenario_id = "pyrit"
    if version is None:
        notes.append("this document does not record the PyRIT version (only the 'full' view does)")
    result = ImportResult(
        tool=TOOL, tool_version=version, source_file=src.name, source_sha256=src.sha256,
        detected_because=reason,
        verification="real run (PyRIT 1.2.0, its JSON printers; the pyrit_scan CLI was not run)",
        observable_channels=BLACK_BOX, notes=notes,
    )
    skipped_kinds: list[str] = []
    seen_channels: set[str] = set()
    for index, conv in enumerate(conversations[:MAX_TRACES]):
        record_id = str(conv.get("id") or conv.get("conversation_id") or index)
        run_id = safe_id(f"{scenario_id}_{index}_{record_id[:8]}", f"pyrit_{index}")
        trace, skipped = trace_from_messages(list(conv.get("messages") or []), run_id=run_id)
        skipped_kinds += skipped
        if not trace.events:
            result.skipped += 1
            continue
        channels = {e.channel_value for e in trace.events}
        seen_channels |= channels
        observable = BLACK_BOX + sorted(channels - set(BLACK_BOX))
        obs = observation(TOOL, observable, _NOTE_TOOLS if channels - set(BLACK_BOX) else _NOTE_BLACK)
        stamp(trace, tool=TOOL, tool_version=version, source_file=src.name,
              source_sha256=src.sha256, record_id=record_id, observation_=obs,
              labels={k: v for k, v in {
                  "technique": conv.get("technique"), "objective": conv.get("objective"),
                  "outcome": conv.get("outcome"), "executed_turns": conv.get("executed_turns"),
                  "score": conv.get("score"), "conversation_id": conv.get("conversation_id"),
              }.items() if v not in (None, "")})
        result.traces.append(ImportedTrace(record_id=record_id, trace=trace))
    result.observable_channels = BLACK_BOX + sorted(seen_channels - set(BLACK_BOX))
    if len(conversations) > MAX_TRACES:
        notes.append(f"stopped after {MAX_TRACES} conversations")
    if skipped_kinds:
        notes.append(f"{len(skipped_kinds)} media piece(s) ({', '.join(sorted(set(skipped_kinds)))}) "
                     "were not read: their value is a file path or URL, which is never opened")
    if result.skipped:
        notes.append(f"{result.skipped} conversation(s) had no text to import")
    return result
