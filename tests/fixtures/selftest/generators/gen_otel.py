# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Emit GenAI semconv spans with the real OTel SDK and encode them as OTLP JSON."""

import json

from google.protobuf.json_format import MessageToDict
from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

exp = InMemorySpanExporter()
tp = TracerProvider()
tp.add_span_processor(SimpleSpanProcessor(exp))
tr = tp.get_tracer("gen")
with tr.start_as_current_span("invoke_agent support") as s:
    s.set_attribute("gen_ai.operation.name", "invoke_agent")
    s.set_attribute("gen_ai.agent.name", "support")
    with tr.start_as_current_span("chat gpt-4o-mini") as c:
        c.set_attribute("gen_ai.operation.name", "chat")
        c.set_attribute(
            "gen_ai.input.messages",
            json.dumps(
                [
                    {
                        "role": "user",
                        "parts": [{"type": "text", "content": "Update the CRM for customer C-7."}],
                    }
                ]
            ),
        )
        c.set_attribute(
            "gen_ai.output.messages",
            json.dumps(
                [
                    {
                        "role": "assistant",
                        "parts": [
                            {
                                "type": "tool_call",
                                "id": "call_9",
                                "name": "crm_update",
                                "arguments": {
                                    "note": "Reached Sam Rivera at sam.rivera@example.com"
                                },
                            }
                        ],
                    }
                ]
            ),
        )
    with tr.start_as_current_span("execute_tool crm_update") as t:
        t.set_attribute("gen_ai.operation.name", "execute_tool")
        t.set_attribute("gen_ai.tool.name", "crm_update")
        t.set_attribute("gen_ai.tool.call.id", "call_9")
        t.set_attribute(
            "gen_ai.tool.call.arguments",
            json.dumps({"note": "Reached Sam Rivera at sam.rivera@example.com"}),
        )
        t.set_attribute("gen_ai.tool.call.result", "saved")
    with tr.start_as_current_span("chat gpt-4o-mini") as c2:
        c2.set_attribute("gen_ai.operation.name", "chat")
        c2.set_attribute(
            "gen_ai.output.messages",
            json.dumps(
                [
                    {
                        "role": "assistant",
                        "parts": [{"type": "text", "content": "The CRM is updated."}],
                        "finish_reason": "stop",
                    }
                ]
            ),
        )
print(json.dumps(MessageToDict(encode_spans(exp.get_finished_spans())), indent=1))
