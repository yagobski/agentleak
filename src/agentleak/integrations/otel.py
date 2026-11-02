# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""OpenTelemetry / OpenInference span integration.

Instead of writing a bespoke adapter per framework, reuse the open-source
**tracing** ecosystem. Arize **OpenInference** and the **OpenTelemetry GenAI**
semantic conventions are already emitted, out of the box, by instrumentors for
LangChain, LlamaIndex, CrewAI, AutoGen, DSPy, Haystack, the OpenAI / Anthropic /
Bedrock SDKs, and more (via Arize Phoenix and Traceloop / OpenLLMetry). If your
stack exports spans, AgentLeak can analyze them directly — no new code per
framework.

This adapter normalizes a list of spans into a :class:`~agentleak.core.trace.Trace`.
A span is duck-typed; pass whichever you have:

- an **OpenInference span dict** with a flattened ``attributes`` dict
  (``{"openinference.span.kind": "TOOL", "input.value": "...", ...}``);
- a raw **OTLP** JSON payload (``{"resourceSpans": [...]}``) from any OTel
  exporter — its attribute list is normalized automatically;
- an object exposing ``.name`` / ``.attributes`` (e.g. a readable span).

Span kind → channel:

==================  ===================================================
OpenInference kind  AgentLeak channel
==================  ===================================================
``TOOL``            ``tool_call`` (arguments) + ``tool_response`` (output)
``RETRIEVER``       ``tool_response`` (retrieved documents — a source)
``LLM``             ``inter_agent_message`` (turn output); the last
                    LLM/CHAIN/AGENT output is promoted to ``final_output``
``CHAIN``/``AGENT``  root input → ``user_input``; output → ``final_output``
``GUARDRAIL``       ``log``
==================  ===================================================

Usage::

    from agentleak.integrations.otel import trace_from_spans
    from agentleak import AgentLeakRunner

    trace = trace_from_spans(spans, run_id="run_001")
    result = AgentLeakRunner().analyze(trace)

Or with the unified API::

    with agentleak.watch("my-agent") as run:
        run.ingest_spans(spans)            # Phoenix / OpenLLMetry export
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from ..core.trace import Channel, Event, Trace

# OpenInference / OTel GenAI attribute keys (with common aliases).
_KIND_KEYS = ("openinference.span.kind", "span.kind", "gen_ai.operation.name")
_INPUT_KEYS = ("input.value", "gen_ai.prompt", "traceloop.entity.input")
_OUTPUT_KEYS = ("output.value", "gen_ai.completion", "traceloop.entity.output")
_TOOL_NAME_KEYS = ("tool.name", "gen_ai.tool.name", "tool_call.function.name")
_TOOL_ARGS_KEYS = ("tool.parameters", "tool_call.function.arguments", "input.value")
_AGENT_KEYS = ("agent.name", "graph.node.name", "graph.node.id", "gen_ai.agent.name")
# Flow context no tracing convention carries; read only when the application
# sets it, never guessed.
_RECIPIENT_KEY = "agentleak.recipient"
_PURPOSE_KEY = "agentleak.purpose"


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        val = getattr(obj, name, None)
        if val is None and isinstance(obj, dict):
            val = obj.get(name)
        if val not in (None, ""):
            return val
    return default


def _otlp_value(v: Any) -> Any:
    """Unwrap an OTLP AnyValue ({"stringValue": "x"}) to a plain Python value."""
    if not isinstance(v, dict):
        return v
    for k in ("stringValue", "boolValue", "doubleValue"):
        if k in v:
            return v[k]
    if "intValue" in v:
        try:
            return int(v["intValue"])
        except (TypeError, ValueError):
            return v["intValue"]
    if "arrayValue" in v:
        return [_otlp_value(x) for x in v["arrayValue"].get("values", [])]
    if "kvlistValue" in v:
        return {kv.get("key"): _otlp_value(kv.get("value")) for kv in v["kvlistValue"].get("values", [])}
    return v


def _attrs_of(span: Any) -> dict[str, Any]:
    """Return a flat attribute dict, normalizing the OTLP attribute-list shape."""
    attrs = _get(span, "attributes", "attr", default=None)
    if attrs is None:
        return {}
    if isinstance(attrs, Mapping):
        # dict, or the SDK's BoundedAttributes on a live ReadableSpan.
        return dict(attrs)
    # OTLP: a list of {"key": ..., "value": {<AnyValue>}}.
    out: dict[str, Any] = {}
    for item in attrs:
        if isinstance(item, dict) and "key" in item:
            out[item["key"]] = _otlp_value(item.get("value"))
    return out


def _spans_from_otlp(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten an OTLP ExportTraceServiceRequest into a list of span dicts."""
    spans: list[dict[str, Any]] = []
    for rs in payload.get("resourceSpans", []):
        for ss in rs.get("scopeSpans", []) or rs.get("instrumentationLibrarySpans", []):
            spans.extend(ss.get("spans", []))
    return spans


def _unflatten_messages(attrs: dict[str, Any], prefix: str) -> list[dict[str, str]]:
    """Rebuild ``[{role, content}]`` from flattened ``<prefix>.<i>.message.*`` keys."""
    by_index: dict[int, dict[str, str]] = {}
    plen = len(prefix) + 1
    for key, value in attrs.items():
        if not key.startswith(prefix + "."):
            continue
        rest = key[plen:]
        idx_str, _, tail = rest.partition(".")
        if not idx_str.isdigit():
            continue
        idx = int(idx_str)
        msg = by_index.setdefault(idx, {})
        if tail.endswith("message.role"):
            msg["role"] = str(value)
        elif tail.endswith("message.content"):
            msg["content"] = str(value)
        elif "tool_call" in tail and tail.endswith("function.name"):
            msg.setdefault("tool_name", str(value))
        elif "tool_call" in tail and tail.endswith("function.arguments"):
            msg.setdefault("tool_args", str(value))
    return [by_index[i] for i in sorted(by_index)]


def _retrieved_docs(attrs: dict[str, Any]) -> str:
    """Concatenate flattened ``retrieval.documents.<i>.document.content`` values."""
    parts: list[str] = []
    for key in sorted(attrs):
        if key.startswith("retrieval.documents.") and key.endswith("document.content"):
            parts.append(str(attrs[key]))
    return "\n\n".join(parts)


def _ms(value: Any) -> float | None:
    """A span time in ms (promptfoo's ``startTime``/``endTime``), if it is one."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _annotate(events: list[Event], span: Any, attrs: dict[str, Any],
              start: float | None, end: float | None) -> None:
    """Keep the span's identity, time and declared flow context on its events."""
    meta = {key: str(value) for key, value in (
        ("span_id", _get(span, "spanId", "span_id")),
        ("parent_span_id", _get(span, "parentSpanId", "parent_span_id")),
        ("purpose", attrs.get(_PURPOSE_KEY)),
    ) if value not in (None, "")}
    recipient = attrs.get(_RECIPIENT_KEY)
    for ev in events:
        ev.metadata.update(meta)
        if ev.channel_value == "inter_agent_message":
            if recipient not in (None, ""):
                ev.target = str(recipient)
            else:
                ev.metadata["target_inferred"] = True   # "agent" is a placeholder
        # Inputs happen when the span starts, outputs when it ends.
        sent_at_start = ev.channel_value == "user_input" or (
            ev.channel_value == "tool_call" and ev.metadata.get("span_kind") != "LLM")
        at = start if sent_at_start else end
        if at is not None:
            ev.timestamp = datetime.fromtimestamp(at / 1000.0, tz=timezone.utc)


def _final_output(events: list[Event], spans: list[Any]) -> Event | None:
    """The user-facing answer: the last model/chain output that declares no
    other recipient and is not nested (by parent span) inside another span
    that produced output. ``None`` when no output qualifies."""
    outputs = [e for e in events if e.channel_value == "inter_agent_message"]
    producers = {e.metadata.get("span_id") for e in outputs}
    parent_of = {str(_get(s, "spanId", "span_id")): str(_get(s, "parentSpanId", "parent_span_id"))
                 for s in spans if _get(s, "parentSpanId", "parent_span_id") is not None}

    def nested(span_id: str | None) -> bool:
        seen: set[str] = set()
        while span_id in parent_of and span_id not in seen:
            seen.add(span_id)
            span_id = parent_of[span_id]
            if span_id in producers:
                return True
        return False

    candidates = [e for e in outputs
                  if (e.metadata.get("target_inferred") or e.target == "user")
                  and not nested(e.metadata.get("span_id"))]
    return candidates[-1] if candidates else None


def trace_from_spans(
    spans: Any,
    *,
    run_id: str = "run",
    agent_name: str = "otel_agent",
    default_agent: str = "agent",
) -> Trace:
    """Build a trace from OpenInference / OTel GenAI spans.

    The last LLM/CHAIN/AGENT textual output is treated as the user-facing
    ``final_output``; earlier model turns are ``inter_agent_message``, so a clean
    final answer never masks an upstream leak. An output whose span declares an
    ``agentleak.recipient`` other than ``user``, or that is nested inside another
    output-producing span, is never the final answer.

    When every span has ``startTime`` and ``endTime`` (ms, as promptfoo sends
    them), events are ordered by when they happened; otherwise document order is
    kept. Events carry ``span_id``, ``parent_span_id``, a declared
    ``agentleak.purpose`` and their time; an output with no declared recipient
    keeps the placeholder target ``"agent"`` and ``metadata["target_inferred"]``.
    """
    if isinstance(spans, dict) and "resourceSpans" in spans:
        spans = _spans_from_otlp(spans)
    spans = list(spans or [])
    times = [(_ms(_get(s, "startTime")), _ms(_get(s, "endTime"))) for s in spans]
    timed = bool(spans) and all(start is not None and end is not None for start, end in times)
    if timed:
        order = sorted(range(len(spans)), key=lambda i: times[i][0] or 0.0)
        spans, times = [spans[i] for i in order], [times[i] for i in order]

    trace = Trace(run_id=run_id, agent_name=agent_name)

    for span, (start, end) in zip(spans, times, strict=True):
        first = len(trace.events)
        attrs = _attrs_of(span)
        kind = str(_get(attrs, *_KIND_KEYS, default="") or "").upper()
        name = str(_get(span, "name", default="") or "")
        agent = str(_get(attrs, *_AGENT_KEYS, default=None) or name or default_agent)

        if kind == "TOOL" or (not kind and _get(attrs, *_TOOL_NAME_KEYS)):
            tool = str(_get(attrs, *_TOOL_NAME_KEYS, default=name or "tool"))
            args = _get(attrs, *_TOOL_ARGS_KEYS)
            if args is not None:
                trace.add_event(channel="tool_call", content=str(args),
                                source=agent, target=tool,
                                metadata={"tool_name": tool, "span_kind": kind or "TOOL", "origin": "otel"})
            out = _get(attrs, *_OUTPUT_KEYS)
            if out is not None:
                trace.add_event(channel="tool_response", content=str(out),
                                source=tool, target=agent,
                                metadata={"tool_name": tool, "origin": "otel"})

        elif kind == "RETRIEVER":
            docs = _retrieved_docs(attrs) or str(_get(attrs, *_OUTPUT_KEYS, default=""))
            if docs:
                trace.add_event(channel="tool_response", content=docs,
                                source=str(name or "retriever"), target=agent,
                                metadata={"span_kind": "RETRIEVER", "origin": "otel"})

        elif kind == "GUARDRAIL":
            val = _get(attrs, *_OUTPUT_KEYS, *_INPUT_KEYS)
            if val is not None:
                trace.add_event(channel="log", content=str(val),
                                source=agent, target="guardrail",
                                metadata={"span_kind": "GUARDRAIL", "origin": "otel"})

        elif kind == "LLM":
            # Tool calls the model emitted are sinks; record each.
            for msg in _unflatten_messages(attrs, "llm.output_messages"):
                if msg.get("tool_args") or msg.get("tool_name"):
                    trace.add_event(channel="tool_call",
                                    content=msg.get("tool_args") or msg.get("tool_name", ""),
                                    source=agent, target=str(msg.get("tool_name", "tool")),
                                    metadata={"span_kind": "LLM", "origin": "otel"})
            out_msgs = _unflatten_messages(attrs, "llm.output_messages")
            text = next((m["content"] for m in reversed(out_msgs) if m.get("content")), None)
            if text is None:
                text = _get(attrs, *_OUTPUT_KEYS)
            if text:
                trace.add_event(channel="inter_agent_message", content=str(text),
                                source=agent, target="agent",
                                metadata={"span_kind": "LLM", "origin": "otel"})

        elif kind in ("CHAIN", "AGENT") or not kind:
            inp = _get(attrs, *_INPUT_KEYS)
            if inp is not None and not trace.events:
                trace.add_event(channel="user_input", content=str(inp),
                                source="user", target=agent,
                                metadata={"span_kind": kind or "CHAIN", "origin": "otel"})
            out = _get(attrs, *_OUTPUT_KEYS)
            if out is not None:
                trace.add_event(channel="inter_agent_message", content=str(out),
                                source=agent, target="agent",
                                metadata={"span_kind": kind or "CHAIN", "origin": "otel"})

        _annotate(trace.events[first:], span, attrs, start, end)

    if timed:
        # Execution order, not document order (the sort is stable); ids follow it.
        trace.events.sort(key=lambda e: e.timestamp)
        for number, ev in enumerate(trace.events, start=1):
            ev.event_id = f"evt_{number:03d}"

    # Promote the final model/chain output to the user-facing channel.
    final = _final_output(trace.events, spans)
    if final is not None:
        final.channel = Channel.FINAL_OUTPUT
        final.target = "user"
        final.metadata["promoted_to"] = "final_output"
        final.metadata.pop("target_inferred", None)

    return trace


__all__ = ["trace_from_spans"]
