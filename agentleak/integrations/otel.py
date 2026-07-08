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

from typing import Any

from ..core.trace import Channel, Trace

# OpenInference / OTel GenAI attribute keys (with common aliases).
_KIND_KEYS = ("openinference.span.kind", "span.kind", "gen_ai.operation.name")
_INPUT_KEYS = ("input.value", "gen_ai.prompt", "traceloop.entity.input")
_OUTPUT_KEYS = ("output.value", "gen_ai.completion", "traceloop.entity.output")
_TOOL_NAME_KEYS = ("tool.name", "gen_ai.tool.name", "tool_call.function.name")
_TOOL_ARGS_KEYS = ("tool.parameters", "tool_call.function.arguments", "input.value")
_AGENT_KEYS = ("agent.name", "graph.node.name", "graph.node.id", "gen_ai.agent.name")


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
    if isinstance(attrs, dict):
        return attrs
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


def trace_from_spans(
    spans: Any,
    *,
    run_id: str = "run",
    agent_name: str = "otel_agent",
    default_agent: str = "agent",
) -> Trace:
    """Build a trace from OpenInference / OTel GenAI spans.

    The last LLM/CHAIN/AGENT textual output (in document order) is treated as the
    user-facing ``final_output``; earlier model turns are ``inter_agent_message``,
    so a clean final answer never masks an upstream leak.
    """
    if isinstance(spans, dict) and "resourceSpans" in spans:
        spans = _spans_from_otlp(spans)
    spans = list(spans or [])

    trace = Trace(run_id=run_id, agent_name=agent_name)
    last_model_event_id: str | None = None

    for span in spans:
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
                ev = trace.add_event(channel="inter_agent_message", content=str(text),
                                     source=agent, target="agent",
                                     metadata={"span_kind": "LLM", "origin": "otel"})
                last_model_event_id = ev.event_id

        elif kind in ("CHAIN", "AGENT") or not kind:
            inp = _get(attrs, *_INPUT_KEYS)
            if inp is not None and not trace.events:
                trace.add_event(channel="user_input", content=str(inp),
                                source="user", target=agent,
                                metadata={"span_kind": kind or "CHAIN", "origin": "otel"})
            out = _get(attrs, *_OUTPUT_KEYS)
            if out is not None:
                ev = trace.add_event(channel="inter_agent_message", content=str(out),
                                     source=agent, target="agent",
                                     metadata={"span_kind": kind or "CHAIN", "origin": "otel"})
                last_model_event_id = ev.event_id

    # Promote the final model/chain output to the user-facing channel.
    if last_model_event_id is not None:
        for ev in trace.events:
            if ev.event_id == last_model_event_id:
                ev.channel = Channel.FINAL_OUTPUT
                ev.target = "user"
                ev.metadata["promoted_to"] = "final_output"
                break

    return trace


__all__ = ["trace_from_spans"]
