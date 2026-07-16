"""Integration adapter tests (no third-party frameworks required)."""

from __future__ import annotations

from agentleak import AgentLeakRunner
from agentleak.integrations.autogen import trace_from_messages
from agentleak.integrations.crewai import CrewAICallback
from agentleak.integrations.generic import TraceRecorder, from_events
from agentleak.integrations.langchain import LangChainCallback
from agentleak.integrations.langgraph import trace_from_state


def test_generic_recorder():
    rec = TraceRecorder(run_id="r")
    rec.tool_call({"email": "a@b.com"}, target="crm")
    rec.final_output("done")
    result = AgentLeakRunner().analyze(rec.trace)
    assert any(f.data_type == "email" for f in result.findings)


def test_from_events_builds_trace():
    trace = from_events([
        {"channel": "tool_call", "content": {"ssn": "123-45-6789"}},
        {"channel": "final_output", "content": "ok"},
    ], run_id="r")
    assert len(trace.events) == 2
    assert trace.events[0].event_id == "evt_001"


def test_langchain_callback_duck_typed():
    cb = LangChainCallback(run_id="r")
    cb.on_tool_start({"name": "crm"}, "lookup customer alex@example.com")
    cb.on_tool_end("account ACC-99887")
    cb.on_text("INFO processed for alex@example.com")
    result = cb.analyze()
    channels = {f.channel for f in result.findings}
    assert "tool_call" in channels
    assert "log" in channels


def test_langchain_agent_action_and_llm_end():
    cb = LangChainCallback(run_id="r")

    class Action:
        tool = "send_email"
        tool_input = {"to": "x@y.com", "body": "ssn 123-45-6789"}

    class Gen:
        text = "Final summary for the user."

    class LLMResult:
        generations = [[Gen()]]

    cb.on_agent_action(Action())
    cb.on_llm_end(LLMResult())
    channels = {e.channel_value for e in cb.trace.events}
    assert "inter_agent_message" in channels
    assert cb.trace.events[-1].channel_value == "final_output"
    result = cb.analyze()
    assert any(f.data_type == "ssn" for f in result.findings)


def test_langchain_llm_end_falls_back_to_str():
    cb = LangChainCallback(run_id="r")
    cb.on_llm_end("plain string response")
    assert cb.trace.events[-1].searchable_text == "plain string response"


def test_langchain_multi_agent_only_last_llm_end_is_final():
    """In a multi-node graph, only the final LLM turn is final_output; earlier
    turns must demote to inter_agent_message so they aren't misattributed to the
    user-facing answer."""
    cb = LangChainCallback(run_id="r")

    def gen(text):
        class Gen:
            pass
        g = Gen()
        g.text = text
        class LLMResult:
            generations = [[g]]
        return LLMResult()

    cb.on_llm_end(gen("triage: fetch the profile, ssn 123-45-6789"))
    cb.on_llm_end(gen("records handoff: email a@b.com phone 514-555-0142"))
    cb.on_llm_end(gen("Your refund is being processed. Thank you!"))

    channels = [e.channel_value for e in cb.trace.events]
    assert channels.count("final_output") == 1
    assert cb.trace.events[-1].channel_value == "final_output"
    assert channels.count("inter_agent_message") == 2
    # The leaked SSN/email now sit on an internal channel, not final_output.
    result = cb.analyze()
    leaked_finals = [f for f in result.leaked_findings() if f.channel == "final_output"]
    assert leaked_finals == []


def test_langgraph_trace_from_state():
    state = {"messages": [
        {"role": "agent", "content": "lookup customer with email a@b.com"},
        {"role": "assistant", "content": "Here is your summary."},
    ]}
    trace = trace_from_state(state, run_id="r")
    assert trace.events[-1].channel_value == "final_output"
    assert trace.events[0].channel_value == "inter_agent_message"


def test_autogen_trace_from_messages():
    trace = trace_from_messages([
        {"name": "researcher", "content": "client ssn is 123-45-6789"},
        {"name": "writer", "content": "Summary complete."},
    ], run_id="r")
    result = AgentLeakRunner().analyze(trace)
    assert trace.events[-1].channel_value == "final_output"
    assert any(f.data_type == "ssn" for f in result.findings)


def test_crewai_callback():
    cb = CrewAICallback(run_id="r")

    class Step:
        tool = "crm"
        tool_input = {"email": "a@b.com"}
        text = "using crm"

    class TaskOut:
        raw = "Final answer to the user."
        agent = "writer"

    cb.step_callback(Step())
    cb.task_callback(TaskOut())
    result = cb.analyze()
    assert any(f.channel == "tool_call" for f in result.findings)
    assert cb.trace.events[-1].channel_value == "final_output"


# -- OpenAI Swarm / Agents SDK ----------------------------------------------
def test_openai_swarm_trace_from_messages():
    from agentleak.integrations.openai_swarm import trace_from_messages as swarm_trace

    messages = [
        {"role": "user", "content": "look up customer 42", "sender": "user"},
        {"role": "assistant", "sender": "triage", "content": "Transferring you to support.",
         "tool_calls": [{"function": {"name": "crm", "arguments": '{"email": "a@b.com"}'}}]},
        {"role": "tool", "sender": "crm", "content": "account ACC-99887 ssn 123-45-6789"},
        {"role": "assistant", "sender": "support", "content": "Here is your summary."},
    ]
    trace = swarm_trace(messages, run_id="r")
    result = AgentLeakRunner().analyze(trace)
    channels = {e.channel_value for e in trace.events}
    assert "tool_call" in channels
    assert "inter_agent_message" in channels  # handoff triage -> support
    assert trace.events[-1].channel_value == "final_output"
    assert any(f.data_type == "ssn" for f in result.findings)


# -- LlamaIndex -------------------------------------------------------------
def test_llamaindex_trace_from_response():
    from agentleak.integrations.llamaindex import trace_from_response

    class ToolOutput:
        tool_name = "crm"
        raw_input = {"kwargs": {"email": "a@b.com"}}
        content = "account ACC-12345 ssn 123-45-6789"

    class Response:
        sources = [ToolOutput()]
        response = "All set."

    trace = trace_from_response(Response(), run_id="r")
    result = AgentLeakRunner().analyze(trace)
    assert any(f.channel == "tool_call" for f in result.findings)
    assert any(f.data_type == "ssn" for f in result.findings)
    assert trace.events[-1].channel_value == "final_output"


def test_llamaindex_callback():
    from agentleak.integrations.llamaindex import LlamaIndexCallback

    cb = LlamaIndexCallback(run_id="r")
    cb.on_event_start("function_call", {"function_call": '{"email": "a@b.com"}', "tool": "crm"})
    cb.on_event_end("function_call", {"function_output": "ssn 123-45-6789"})
    result = cb.analyze()
    channels = {f.channel for f in result.findings}
    assert "tool_call" in channels
    assert "tool_response" in channels


# -- Semantic Kernel --------------------------------------------------------
def test_semantic_kernel_trace_from_chat_history():
    from agentleak.integrations.semantic_kernel import trace_from_chat_history

    class FnCall:
        function_name = "crm"
        arguments = {"email": "a@b.com"}

    class Msg:
        def __init__(self, role, content, name, items=None):
            self.role = role
            self.content = content
            self.name = name
            self.items = items or []

    messages = [
        Msg("user", "look up the client", "user"),
        Msg("assistant", "calling crm", "researcher", items=[FnCall()]),
        Msg("assistant", "client ssn is 123-45-6789", "writer"),
        Msg("assistant", "Final summary.", "writer"),
    ]
    trace = trace_from_chat_history(messages, run_id="r")
    result = AgentLeakRunner().analyze(trace)
    channels = {e.channel_value for e in trace.events}
    assert "tool_call" in channels
    assert "inter_agent_message" in channels
    assert trace.events[-1].channel_value == "final_output"
    assert any(f.data_type == "ssn" for f in result.findings)


# -- Pydantic AI ------------------------------------------------------------
def test_pydantic_ai_trace_from_messages():
    from agentleak.integrations.pydantic_ai import trace_from_messages as pai_trace

    class Part:
        def __init__(self, kind, content=None, tool_name=None, args=None):
            self.part_kind = kind
            self.content = content
            self.tool_name = tool_name
            self.args = args

    class Message:
        def __init__(self, parts):
            self.parts = parts

    messages = [
        Message([Part("user-prompt", content="look up the client")]),
        Message([Part("tool-call", tool_name="crm", args={"email": "a@b.com"})]),
        Message([Part("tool-return", tool_name="crm", content="ssn 123-45-6789")]),
        Message([Part("text", content="Here is the final answer.")]),
    ]
    trace = pai_trace(messages, run_id="r")
    result = AgentLeakRunner().analyze(trace)
    channels = {e.channel_value for e in trace.events}
    assert "tool_call" in channels
    assert "tool_response" in channels
    assert trace.events[-1].channel_value == "final_output"
    assert any(f.data_type == "ssn" for f in result.findings)


# -- smolagents -------------------------------------------------------------
def test_smolagents_trace_from_steps():
    from agentleak.integrations.smolagents import trace_from_steps

    class ToolCall:
        name = "crm"
        arguments = {"email": "a@b.com"}

    class TaskStep:
        task = "look up the client"

    class ActionStep:
        model_output = "I will call crm"
        tool_calls = [ToolCall()]
        observations = "client ssn 123-45-6789"
        action_output = "Final answer."
        is_final_answer = True

    trace = trace_from_steps([TaskStep(), ActionStep()], run_id="r")
    result = AgentLeakRunner().analyze(trace)
    channels = {e.channel_value for e in trace.events}
    assert "user_input" in channels
    assert "tool_call" in channels
    assert trace.events[-1].channel_value == "final_output"
    assert any(f.data_type == "ssn" for f in result.findings)


# -- Google ADK -------------------------------------------------------------
def test_google_adk_trace_from_events():
    from agentleak.integrations.google_adk import trace_from_events

    class FunctionCall:
        name = "crm"
        args = {"email": "a@b.com"}

    class FunctionResponse:
        name = "crm"
        response = "ssn 123-45-6789"

    class Part:
        def __init__(self, text=None, function_call=None, function_response=None):
            self.text = text
            self.function_call = function_call
            self.function_response = function_response

    class Content:
        def __init__(self, parts):
            self.parts = parts

    class Event:
        def __init__(self, author, parts, final=False):
            self.author = author
            self.content = Content(parts)
            self._final = final

        def is_final_response(self):
            return self._final

    events = [
        Event("user", [Part(text="look up the client")]),
        Event("researcher", [Part(function_call=FunctionCall())]),
        Event("researcher", [Part(function_response=FunctionResponse())]),
        Event("writer", [Part(text="Here is your summary.")], final=True),
    ]
    trace = trace_from_events(events, run_id="r")
    result = AgentLeakRunner().analyze(trace)
    channels = {e.channel_value for e in trace.events}
    assert "tool_call" in channels
    assert "tool_response" in channels
    assert trace.events[-1].channel_value == "final_output"
    assert any(f.data_type == "ssn" for f in result.findings)


# -- Registry ---------------------------------------------------------------
def test_registry_lists_new_frameworks():
    from agentleak.integrations import registry

    ids = set(registry.framework_ids())
    for fid in ("openai_swarm", "llamaindex", "semantic_kernel",
                "pydantic_ai", "smolagents", "google_adk", "computer_use",
                "openinference", "mcp"):
        assert fid in ids
        snippet = registry.snippet_for(fid, "demo")
        assert "agentleak.watch" in snippet


def test_mcp_trace_from_calls():
    from agentleak.integrations.mcp import trace_from_mcp

    trace = trace_from_mcp([
        {"server": "github-mcp", "tool": "create_issue",
         "arguments": {"title": "Bug", "body": "reach me at jane@example.com, ssn 123-45-6789"},
         "result": "issue #42 created", "agent": "Researcher"},
    ], run_id="r")

    calls = [e for e in trace.events if e.channel_value == "tool_call"]
    responses = [e for e in trace.events if e.channel_value == "tool_response"]
    assert calls and responses
    # The MCP server is a named sink node; the call carries the secret to it.
    assert calls[0].target == "mcp:github-mcp/create_issue"
    assert calls[0].source == "Researcher"
    assert "123-45-6789" in calls[0].searchable_text

    result = AgentLeakRunner().analyze(trace)
    # Sending PII to an MCP tool is a leak (tool_call is not a baseline channel).
    assert any(f.data_type == "ssn" for f in result.findings)


def test_computer_use_trace_from_steps():
    from agentleak.integrations.computer_use import trace_from_steps

    steps = [
        {"action": "read_file", "path": "customer_C001.yaml",
         "observation": "ssn: 456-78-9012\nemail: marie@example.com"},
        {"action": "run_shell", "command": "export DSN=postgresql://app:S3cr3t@db:5432/x",
         "observation": "(executed)"},
        {"action": "think", "thought": "the customer's ssn is 456-78-9012"},
        {"action": "write_file", "path": "incident_report.md",
         "content": "Customer ssn 456-78-9012, email marie@example.com"},
        {"action": "finish", "content": "All done, report written. No PII here."},
    ]
    trace = trace_from_steps(steps, run_id="r")
    channels = {e.channel_value for e in trace.events}

    # The file the agent wrote is on the generated_file channel.
    gen = [e for e in trace.events if e.channel_value == "generated_file"]
    assert gen and gen[0].target == "incident_report.md"
    assert "456-78-9012" in gen[0].searchable_text
    # Reading a file is a source (tool_response); shell command is a tool_call;
    # reasoning is a log; the last message is the user-facing final_output.
    assert {"tool_response", "tool_call", "log", "generated_file", "final_output"} <= channels
    assert trace.events[-1].channel_value == "final_output"

    result = AgentLeakRunner().analyze(trace)
    leaked = result.leaked_findings()
    # The SSN persisted to disk and the DB secret in shell are leaks; the file
    # is NOT a baseline channel so it counts.
    assert any(f.channel == "generated_file" and f.data_type == "ssn" for f in leaked)
    # The clean final answer does not, by itself, carry the SSN.
    finals = [f for f in leaked if f.channel == "final_output"]
    assert not any(f.data_type == "ssn" for f in finals)


def test_openinference_trace_from_spans():
    from agentleak.integrations.otel import trace_from_spans

    spans = [
        {"name": "agent", "attributes": {
            "openinference.span.kind": "CHAIN", "input.value": "look up customer C001"}},
        {"name": "crm", "attributes": {
            "openinference.span.kind": "TOOL", "tool.name": "crm_lookup",
            "input.value": '{"id": "C001"}',
            "output.value": "name: Marie Tremblay, ssn: 456-78-9012"}},
        {"name": "llm1", "attributes": {
            "openinference.span.kind": "LLM",
            "llm.output_messages.0.message.role": "assistant",
            "llm.output_messages.0.message.content": "forwarding ssn 456-78-9012 to billing"}},
        {"name": "llm2", "attributes": {
            "openinference.span.kind": "LLM",
            "llm.output_messages.0.message.role": "assistant",
            "llm.output_messages.0.message.content": "Your refund is processing. No PII here."}},
    ]
    trace = trace_from_spans(spans, run_id="r")
    channels = [e.channel_value for e in trace.events]

    assert channels[0] == "user_input"
    assert "tool_call" in channels and "tool_response" in channels
    # Only the LAST model output is the user-facing answer; the earlier turn is
    # an internal handoff.
    assert trace.events[-1].channel_value == "final_output"
    assert "No PII" in str(trace.events[-1].content)
    inter = [e for e in trace.events if e.channel_value == "inter_agent_message"]
    assert any("456-78-9012" in e.searchable_text for e in inter)

    result = AgentLeakRunner().analyze(trace)
    leaked = result.leaked_findings()
    # The SSN leaks on the internal handoff; the clean final answer does not.
    assert any(f.channel == "inter_agent_message" and f.data_type == "ssn" for f in leaked)
    assert not any(f.channel == "final_output" and f.data_type == "ssn" for f in leaked)
    # tool_response is a baseline source, so the SSN arriving from the CRM is not a leak.
    assert not any(f.channel == "tool_response" for f in leaked)


def test_openinference_accepts_raw_otlp_payload():
    from agentleak.integrations.otel import trace_from_spans

    # OTLP wire shape: attributes are a list of {key, value:{stringValue}}.
    otlp = {"resourceSpans": [{"scopeSpans": [{"spans": [
        {"name": "crm", "attributes": [
            {"key": "openinference.span.kind", "value": {"stringValue": "TOOL"}},
            {"key": "tool.name", "value": {"stringValue": "crm"}},
            {"key": "tool_call.function.arguments", "value": {"stringValue": '{"email": "jane@example.com"}'}},
        ]},
    ]}]}]}
    trace = trace_from_spans(otlp, run_id="r")
    calls = [e for e in trace.events if e.channel_value == "tool_call"]
    assert calls and "jane@example.com" in calls[0].searchable_text


# -- OTel/OpenInference edge cases: nested OTLP values, missing attributes --

def test_otel_otlp_nested_value_types_are_unwrapped():
    """Every OTLP AnyValue variant (bool/int/double/array/kvlist) must unwrap
    to a plain Python value, not a leftover ``{"boolValue": ...}`` dict."""
    from agentleak.integrations.otel import _otlp_value

    assert _otlp_value({"stringValue": "x"}) == "x"
    assert _otlp_value({"boolValue": True}) is True
    assert _otlp_value({"doubleValue": 1.5}) == 1.5
    assert _otlp_value({"intValue": "42"}) == 42
    assert _otlp_value({"intValue": "not-a-number"}) == "not-a-number"  # graceful fallback
    assert _otlp_value({"arrayValue": {"values": [{"stringValue": "a"}, {"intValue": "2"}]}}) == ["a", 2]
    assert _otlp_value(
        {"kvlistValue": {"values": [{"key": "k", "value": {"stringValue": "v"}}]}}
    ) == {"k": "v"}
    # A plain (non-AnyValue) scalar passes through unchanged.
    assert _otlp_value(7) == 7
    assert _otlp_value("plain") == "plain"


def test_otel_missing_attributes_produces_no_crash_and_no_events():
    """A span dict/object with no ``attributes`` key at all is tolerated."""
    from agentleak.integrations.otel import trace_from_spans

    trace = trace_from_spans([{"name": "bare_span"}], run_id="r")
    assert trace.events == []


def test_otel_span_object_is_duck_typed_not_only_dicts():
    """Spans can be objects exposing ``.name``/``.attributes`` (e.g. a readable
    OTel span), not just dicts."""
    from agentleak.integrations.otel import trace_from_spans

    class Span:
        def __init__(self, name, attributes):
            self.name = name
            self.attributes = attributes

    spans = [Span("crm", {
        "openinference.span.kind": "TOOL",
        "tool.name": "crm",
        "output.value": "ssn: 456-78-9012",
    })]
    trace = trace_from_spans(spans, run_id="r")
    resp = [e for e in trace.events if e.channel_value == "tool_response"]
    assert resp and "456-78-9012" in resp[0].searchable_text


def test_otel_retriever_span_is_a_source_not_a_leak():
    from agentleak.integrations.otel import trace_from_spans

    spans = [{"name": "retriever", "attributes": {
        "openinference.span.kind": "RETRIEVER",
        "retrieval.documents.0.document.content": "client ssn 456-78-9012",
    }}]
    trace = trace_from_spans(spans, run_id="r")
    resp = [e for e in trace.events if e.channel_value == "tool_response"]
    assert resp and "456-78-9012" in resp[0].searchable_text
    assert resp[0].source == "retriever"


def test_otel_guardrail_span_records_log_channel():
    from agentleak.integrations.otel import trace_from_spans

    spans = [{"name": "pii_filter", "attributes": {
        "openinference.span.kind": "GUARDRAIL",
        "output.value": "blocked: ssn detected",
    }}]
    trace = trace_from_spans(spans, run_id="r")
    logs = [e for e in trace.events if e.channel_value == "log"]
    assert logs and logs[0].target == "guardrail"


def test_otel_llm_span_tool_call_message_recorded():
    """An LLM span whose output message itself is a tool call (rather than
    plain text) must be recorded as a tool_call, not silently dropped."""
    from agentleak.integrations.otel import trace_from_spans

    spans = [{"name": "llm", "attributes": {
        "openinference.span.kind": "LLM",
        "llm.output_messages.0.message.role": "assistant",
        "llm.output_messages.0.tool_call.function.name": "crm_lookup",
        "llm.output_messages.0.tool_call.function.arguments": '{"ssn": "456-78-9012"}',
    }}]
    trace = trace_from_spans(spans, run_id="r")
    calls = [e for e in trace.events if e.channel_value == "tool_call"]
    assert calls and "456-78-9012" in calls[0].searchable_text
    assert calls[0].target == "crm_lookup"


def test_otel_empty_span_list_produces_empty_trace():
    from agentleak.integrations.otel import trace_from_spans

    trace = trace_from_spans([], run_id="r")
    assert trace.events == []
    trace_none = trace_from_spans(None, run_id="r")
    assert trace_none.events == []


# -- computer-use edge cases: unknown/failed actions ------------------------

def test_computer_use_unknown_action_defaults_to_run():
    """An action name that matches none of the known verb buckets is still
    recorded (as a 'run' tool_call), never silently dropped."""
    from agentleak.integrations.computer_use import trace_from_steps

    steps = [{"action": "TeleportAction", "command": "beam me up", "observation": "ok"}]
    trace = trace_from_steps(steps, run_id="r")
    calls = [e for e in trace.events if e.channel_value == "tool_call"]
    assert calls and calls[0].target == "TeleportAction"


def test_computer_use_failed_shell_command_still_captured():
    """A failed action's error observation is still a tool_response — the
    adapter doesn't distinguish success/failure, so failures are not lost."""
    from agentleak.integrations.computer_use import trace_from_steps

    steps = [{"action": "run_shell", "command": "cat /etc/shadow",
              "observation": "Error: Permission denied (exit code 1) for ssn 456-78-9012"}]
    trace = trace_from_steps(steps, run_id="r")
    resp = [e for e in trace.events if e.channel_value == "tool_response"]
    assert resp and "Permission denied" in str(resp[0].content)
    assert "456-78-9012" in resp[0].searchable_text


def test_computer_use_browse_action_records_call_and_response():
    from agentleak.integrations.computer_use import trace_from_steps

    steps = [{"action": "click", "url": "https://forms.example.com/submit",
              "observation": "submitted: ssn 456-78-9012"}]
    trace = trace_from_steps(steps, run_id="r")
    calls = [e for e in trace.events if e.channel_value == "tool_call"]
    resp = [e for e in trace.events if e.channel_value == "tool_response"]
    assert calls and calls[0].target == "https://forms.example.com/submit"
    assert resp and "456-78-9012" in resp[0].searchable_text


def test_computer_use_non_final_finish_step_is_inter_agent_message():
    """Only the LAST 'finish'-kind step is promoted to final_output; an
    earlier one (e.g. a sub-agent's completion message) is internal."""
    from agentleak.integrations.computer_use import trace_from_steps

    steps = [
        {"action": "finish", "content": "Sub-task done: ssn 456-78-9012 verified.", "agent": "sub"},
        {"action": "finish", "content": "All done. No PII in this summary.", "agent": "main"},
    ]
    trace = trace_from_steps(steps, run_id="r")
    inter = [e for e in trace.events if e.channel_value == "inter_agent_message"]
    finals = [e for e in trace.events if e.channel_value == "final_output"]
    assert inter and "456-78-9012" in inter[0].searchable_text
    assert finals and finals[0].content == "All done. No PII in this summary."


# -- End-to-end: every adapter yields a valid AgentRisk-scored result -------
def test_all_adapters_produce_agentrisk_score():
    """Each framework adapter must yield a trace the runner can score, with a
    well-formed AgentRisk report (RI in [0, 1], WSL <= rho_S)."""
    from agentleak.integrations.google_adk import trace_from_events as adk
    from agentleak.integrations.openai_swarm import trace_from_messages as swarm
    from agentleak.integrations.pydantic_ai import trace_from_messages as pai
    from agentleak.integrations.semantic_kernel import trace_from_chat_history as sk
    from agentleak.integrations.smolagents import trace_from_steps as smol

    class Obj:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    traces = {
        "swarm": swarm([
            {"role": "assistant", "sender": "a", "content": "client ssn 123-45-6789"},
        ], run_id="r"),
        "semantic_kernel": sk([
            Obj(role="assistant", content="client ssn 123-45-6789", name="a", items=[]),
        ], run_id="r"),
        "pydantic_ai": pai([
            Obj(parts=[Obj(part_kind="text", content="client ssn 123-45-6789")]),
        ], run_id="r"),
        "smolagents": smol([
            Obj(task=None, model_output="", tool_calls=[],
                observations="client ssn 123-45-6789", action_output="done",
                is_final_answer=True),
        ], run_id="r"),
        "google_adk": adk([
            Obj(author="a", content=Obj(parts=[Obj(text="client ssn 123-45-6789",
                function_call=None, function_response=None)]), _final=True,
                is_final_response=lambda: True),
        ], run_id="r"),
    }

    for name, trace in traces.items():
        result = AgentLeakRunner().analyze(trace)
        report = result.score.agentrisk
        assert 0.0 <= report.ri_global <= 1.0, name
        assert report.wsl <= report.rho_s, name
        assert any(f.data_type == "ssn" for f in result.findings), name


