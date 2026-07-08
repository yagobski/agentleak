# Integrations

AgentLeak analyzes a `Trace`. The fastest way to produce one is the unified
`agentleak.watch()` context manager; the lower-level options below all still
work and are what `watch()` builds on.

## 0. The one-line API: `agentleak.watch()` (recommended)

One import, one context manager. It auto-analyzes on exit and, if a platform is
running, uploads the run to your project. The same block works for **every**
framework via `run.callback`, `run.crew`, `run.ingest_messages()`,
`run.ingest_steps()`, `run.ingest_adk()`, or the channel shortcuts.

```python
import agentleak

with agentleak.watch("my-agent") as run:
    # --- pick whichever fits your stack ---
    chain.invoke(inputs, config={"callbacks": [run.callback]})   # LangChain / LangGraph
    run.ingest_messages(response.messages)                       # OpenAI Swarm / Agents SDK
    run.ingest_steps(agent.steps)                                # computer-use / coding agent
    run.tool_call({"ssn": "123-45-6789"}, target="db")           # direct, any framework
    run.final_output("All set!")

print(run.report.risk_index, run.report.verdict)
```

The rest of this page documents the building blocks.

## 1. By hand / from JSON

Write a trace JSON file and run `agentleak run --trace trace.json`. See
[Concepts](concepts.md) for the format.

## 2. SDK trace builder

```python
from agentleak import Trace, AgentLeakRunner

trace = Trace(run_id="run_001", agent_name="my_agent")
trace.add_event(channel="tool_call", source="agent", target="crm",
                content={"customer_email": "test@example.com"})
trace.add_event(channel="final_output", content="Done.")

result = AgentLeakRunner().analyze(trace)
```

## 3. The `@monitor` decorator

Record live calls without restructuring your code. It's a no-op outside a
`capture()` block, so it's safe to leave in place.

```python
from agentleak import capture, monitor

@monitor(channel="tool_call")
def call_crm(customer_id):
    return crm.get_customer(customer_id)

with capture(run_id="run_001") as cap:
    call_crm(42)

result = cap.analyze()
```

## 4. Framework adapters

None of these import their target framework at module load time, so importing
them is always safe.

### LangChain

```python
from agentleak.integrations.langchain import LangChainCallback

cb = LangChainCallback(run_id="run_001")
chain.invoke(inputs, config={"callbacks": [cb]})
result = cb.analyze()
```

Maps `on_tool_start`→`tool_call`, `on_tool_end`→`tool_response`,
`on_llm_end`→`final_output`, `on_agent_action`→`inter_agent_message`,
`on_text`→`log`.

### LangGraph

```python
from agentleak.integrations.langgraph import AgentLeakCallback, trace_from_state

cb = AgentLeakCallback(run_id="run_001")
graph.invoke(inputs, config={"callbacks": [cb]})
result = cb.analyze()

# or ingest a final graph state:
trace = trace_from_state(final_state, run_id="run_001")
```

### CrewAI

```python
from agentleak.integrations.crewai import CrewAICallback

cb = CrewAICallback(run_id="run_001")
crew = Crew(agents=[...], tasks=[...],
            step_callback=cb.step_callback, task_callback=cb.task_callback)
crew.kickoff()
result = cb.analyze()
```

### AutoGen

```python
from agentleak.integrations.autogen import trace_from_messages
from agentleak import AgentLeakRunner

trace = trace_from_messages(chat_result.chat_history, run_id="run_001")
result = AgentLeakRunner().analyze(trace)
```

### OpenAI Swarm / Agents SDK

Multi-agent handoffs are surfaced as `inter_agent_message` events.

```python
from agentleak.integrations.openai_swarm import trace_from_messages
from agentleak import AgentLeakRunner

response = client.run(agent=triage, messages=[...])
trace = trace_from_messages(response.messages, run_id="run_001")
result = AgentLeakRunner().analyze(trace)
```

### LlamaIndex

Ingests `response.sources` (tool calls/outputs) from a `FunctionAgent`,
`ReActAgent`, or multi-agent `AgentWorkflow`. A duck-typed `LlamaIndexCallback`
is also available for live `CallbackManager` instrumentation.

```python
from agentleak.integrations.llamaindex import trace_from_response
from agentleak import AgentLeakRunner

response = await agent.run("...")
trace = trace_from_response(response, run_id="run_001")
result = AgentLeakRunner().analyze(trace)
```

### Semantic Kernel

Normalizes a `ChatHistory` from a `ChatCompletionAgent` or multi-agent
`AgentGroupChat`; turns from different agents become `inter_agent_message`.

```python
from agentleak.integrations.semantic_kernel import trace_from_chat_history
from agentleak import AgentLeakRunner

trace = trace_from_chat_history(chat.history, run_id="run_001")
result = AgentLeakRunner().analyze(trace)
```

### Pydantic AI

```python
from agentleak.integrations.pydantic_ai import trace_from_messages
from agentleak import AgentLeakRunner

result = await agent.run("...")
trace = trace_from_messages(result.all_messages(), run_id="run_001")
analysis = AgentLeakRunner().analyze(trace)
```

### smolagents

```python
from agentleak.integrations.smolagents import trace_from_steps
from agentleak import AgentLeakRunner

agent.run("...")
trace = trace_from_steps(agent.memory.steps, run_id="run_001")
result = AgentLeakRunner().analyze(trace)
```

### Google ADK

```python
from agentleak.integrations.google_adk import trace_from_events
from agentleak import AgentLeakRunner

events = list(runner.run(user_id="u", session_id="s", new_message=msg))
trace = trace_from_events(events, run_id="run_001")
result = AgentLeakRunner().analyze(trace)
```

### Computer-use / coding agents (OpenHands, Open Interpreter, Cline, SWE-agent, browser-use)

Autonomous agents that **act** rather than chat — they run shell, execute code,
drive a browser, and **write files**. Their most dangerous leakage surface is
the artifact they persist to disk, which a chat-only audit never opens. Hand the
agent's action–observation history to `trace_from_steps`; each step is a
duck-typed dict, so no framework import is required.

```python
from agentleak.integrations.computer_use import trace_from_steps
from agentleak import AgentLeakRunner

steps = [
    {"action": "read_file",  "path": "customer.yaml", "observation": "ssn: 456-78-9012"},
    {"action": "run_shell",  "command": "export DSN=postgresql://app:secret@db/x"},
    {"action": "write_file", "path": "report.md", "content": "...ssn 456-78-9012..."},
    {"action": "finish",     "content": "Report written."},
]
trace = trace_from_steps(steps, run_id="run_001")
result = AgentLeakRunner().analyze(trace)
```

Mapping: file **writes/edits/creates** → `generated_file`; file **reads** →
`tool_response` (a source); **shell / code** → `tool_call` (+ `tool_response`
for the observation); **browser** actions → `tool_call`; agent **reasoning /
scratchpad** → `log`; the final **message** → `final_output`. Action names are
matched by keyword, so `FileWriteAction`, `write_to_file`, and `create` all map
the same way.

### OpenTelemetry / OpenInference (reuse your existing tracing)

If you already trace your app with **Arize Phoenix** or **OpenLLMetry /
Traceloop**, you don't need a per-framework adapter at all. Those emit
[OpenInference](https://github.com/Arize-ai/openinference) /
[OpenTelemetry GenAI](https://opentelemetry.io/docs/specs/semconv/gen-ai/) spans
for LangChain, LlamaIndex, CrewAI, AutoGen, DSPy, Haystack, and the
OpenAI / Anthropic / Bedrock SDKs — AgentLeak ingests those spans directly.

```python
from agentleak.integrations.otel import trace_from_spans
from agentleak import AgentLeakRunner

# `spans` may be a list of OpenInference span dicts (flattened attributes),
# readable-span objects, or a raw OTLP {"resourceSpans": [...]} payload.
trace = trace_from_spans(spans, run_id="run_001")
result = AgentLeakRunner().analyze(trace)
```

Mapping: `TOOL` spans → `tool_call` (arguments) + `tool_response` (output);
`RETRIEVER` → `tool_response` (retrieved docs); `LLM` turns →
`inter_agent_message`, with the **last** model/chain output promoted to
`final_output`; `GUARDRAIL` → `log`. The flattened
`llm.output_messages.<i>.message.content` and `retrieval.documents.<i>...`
attributes are un-flattened for you.

### Anything else

Use the generic recorder and map your framework's events onto channels:

```python
from agentleak.integrations.generic import TraceRecorder
from agentleak import AgentLeakRunner

rec = TraceRecorder(run_id="run_001")
rec.tool_call({"ssn": "123-45-6789"}, target="db")
rec.shared_memory("cached customer record ...")
rec.final_output("All set!")

result = AgentLeakRunner().analyze(rec.trace)
```
