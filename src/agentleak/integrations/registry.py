# SPDX-FileCopyrightText: 2026 AgentLeak contributors
# SPDX-License-Identifier: MIT
"""Registry of agent frameworks.

The single source of truth for which agent frameworks AgentLeak supports, their
display labels, and the SDK connection snippet shown in the platform's *Connect*
tab. Adding a new framework is one :func:`register` call — it then appears in the
project agent-type picker and gets a Connect snippet automatically.

This mirrors how promptfoo treats plugins/providers as a registry rather than a
hardcoded list, but stays scoped to AgentLeak's trace-ingestion model.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

_HEAD = "# pip install 'agentleak'  ·  start the platform with: agentleak serve"


@dataclass(frozen=True)
class AgentFramework:
    id: str
    label: str
    snippet: Callable[[str], str]  # project_name -> python code
    docs: str = ""


_REGISTRY: dict[str, AgentFramework] = {}


def register(framework: AgentFramework) -> None:
    _REGISTRY[framework.id] = framework


def get(framework_id: str) -> AgentFramework | None:
    return _REGISTRY.get(framework_id)


def frameworks() -> list[dict[str, str]]:
    return [{"id": f.id, "label": f.label} for f in _REGISTRY.values()]


def framework_ids() -> list[str]:
    return list(_REGISTRY)


def label_for(framework_id: str) -> str:
    f = _REGISTRY.get(framework_id)
    return f.label if f else framework_id


def snippet_for(framework_id: str, project_name: str) -> str:
    f = _REGISTRY.get(framework_id) or _REGISTRY["generic"]
    return f.snippet(project_name)


# ----------------------------------------------------------------------
# Built-in frameworks
# ----------------------------------------------------------------------
def _generic(p: str) -> str:
    return f"""{_HEAD}
import agentleak

# One context manager. Auto-analyzes on exit and uploads to this project.
with agentleak.watch({p!r}) as run:
    run.tool_call({{"email": "test@example.com", "account_id": "ACC-12345"}}, target="crm")
    run.inter_agent_message("forwarding full profile to billing agent")
    run.final_output("All set!")          # your agent runs inside the block

print(run.report.risk_index, run.report.verdict)"""


def _langchain(p: str) -> str:
    return f"""{_HEAD}
import agentleak

with agentleak.watch({p!r}) as run:
    chain.invoke(inputs, config={{"callbacks": [run.callback]}})

print(run.report.risk_index, run.report.verdict)"""


def _langgraph(p: str) -> str:
    return f"""{_HEAD}
import agentleak

with agentleak.watch({p!r}) as run:
    graph.invoke(inputs, config={{"callbacks": [run.callback]}})

print(run.report.risk_index, run.report.verdict)"""


def _crewai(p: str) -> str:
    return f"""{_HEAD}
import agentleak

with agentleak.watch({p!r}) as run:
    Crew(agents=[...], tasks=[...],
         step_callback=run.crew.step_callback,
         task_callback=run.crew.task_callback).kickoff()

print(run.report.risk_index, run.report.verdict)"""


def _autogen(p: str) -> str:
    return f"""{_HEAD}
import agentleak
from agentleak.integrations.autogen import trace_from_messages

with agentleak.watch({p!r}) as run:
    run.ingest(trace_from_messages(chat_result.chat_history))

print(run.report.risk_index, run.report.verdict)"""


def _openai_swarm(p: str) -> str:
    return f"""{_HEAD}
import agentleak

# OpenAI Swarm / Agents SDK — multi-agent handoffs surface as inter_agent_message.
with agentleak.watch({p!r}) as run:
    response = swarm.run(agent=triage, messages=[...])   # your run
    run.ingest_messages(response.messages)

print(run.report.risk_index, run.report.verdict)"""


def _llamaindex(p: str) -> str:
    return f"""{_HEAD}
import agentleak
from agentleak.integrations.llamaindex import trace_from_response

with agentleak.watch({p!r}) as run:
    response = await agent.run("...")          # FunctionAgent / AgentWorkflow
    run.ingest(trace_from_response(response))

print(run.report.risk_index, run.report.verdict)"""


def _semantic_kernel(p: str) -> str:
    return f"""{_HEAD}
import agentleak
from agentleak.integrations.semantic_kernel import trace_from_chat_history

with agentleak.watch({p!r}) as run:
    run.ingest(trace_from_chat_history(chat.history))

print(run.report.risk_index, run.report.verdict)"""


def _pydantic_ai(p: str) -> str:
    return f"""{_HEAD}
import agentleak
from agentleak.integrations.pydantic_ai import trace_from_messages

with agentleak.watch({p!r}) as run:
    result = await agent.run("...")
    run.ingest(trace_from_messages(result.all_messages()))

print(run.report.risk_index, run.report.verdict)"""


def _smolagents(p: str) -> str:
    return f"""{_HEAD}
import agentleak
from agentleak.integrations.smolagents import trace_from_steps

with agentleak.watch({p!r}) as run:
    agent.run("...")
    run.ingest(trace_from_steps(agent.memory.steps))

print(run.report.risk_index, run.report.verdict)"""


def _google_adk(p: str) -> str:
    return f"""{_HEAD}
import agentleak

with agentleak.watch({p!r}) as run:
    events = list(runner.run(user_id="u", session_id="s", new_message=msg))
    run.ingest_adk(events)

print(run.report.risk_index, run.report.verdict)"""


def _openinference(p: str) -> str:
    return f"""{_HEAD}
import agentleak

# Reuse your existing OpenTelemetry / OpenInference tracing (Arize Phoenix,
# OpenLLMetry). Works for LangChain, LlamaIndex, CrewAI, AutoGen, DSPy, the
# OpenAI/Anthropic/Bedrock SDKs — anything already emitting GenAI spans.
with agentleak.watch({p!r}) as run:
    run.ingest_spans(spans)   # a span list, or a raw OTLP {{resourceSpans}} dict

print(run.report.risk_index, run.report.verdict)"""


def _computer_use(p: str) -> str:
    return f"""{_HEAD}
import agentleak

# OpenHands / Open Interpreter / Cline / SWE-agent / browser-use — agents that
# run shell, execute code, and WRITE FILES. Files they generate are scanned on
# the generated_file channel; secrets in shell/code on tool_call; reasoning on log.
with agentleak.watch({p!r}) as run:
    agent.run("...")                 # your computer-use / coding agent
    run.ingest_steps(agent.steps)   # action-observation history (duck-typed dicts)

print(run.report.risk_index, run.report.verdict)"""


def _mcp(p: str) -> str:
    return f"""{_HEAD}
import agentleak
from agentleak.integrations.mcp import trace_from_mcp

# Record each MCP tool call your agent makes (server, tool, arguments, result).
calls = [
    {{"server": "github-mcp", "tool": "create_issue",
      "arguments": {{"title": "Bug", "body": "contact jane@example.com"}},
      "result": "issue #42 created", "agent": "Researcher"}},
]
with agentleak.watch({p!r}) as run:
    run.ingest(trace_from_mcp(calls))

print(run.report.risk_index, run.report.verdict)"""


for _fw in (
    AgentFramework("generic", "Generic / SDK", _generic),
    AgentFramework("langchain", "LangChain", _langchain),
    AgentFramework("langgraph", "LangGraph", _langgraph),
    AgentFramework("crewai", "CrewAI", _crewai),
    AgentFramework("autogen", "AutoGen", _autogen),
    AgentFramework("openai_swarm", "OpenAI Swarm / Agents SDK", _openai_swarm),
    AgentFramework("llamaindex", "LlamaIndex", _llamaindex),
    AgentFramework("semantic_kernel", "Semantic Kernel", _semantic_kernel),
    AgentFramework("pydantic_ai", "Pydantic AI", _pydantic_ai),
    AgentFramework("smolagents", "smolagents", _smolagents),
    AgentFramework("google_adk", "Google ADK", _google_adk),
    AgentFramework("computer_use", "Computer-use / Coding agent (OpenHands, Cline, Open Interpreter)", _computer_use),
    AgentFramework("openinference", "OpenTelemetry / OpenInference (Phoenix, OpenLLMetry)", _openinference),
    AgentFramework("mcp", "MCP (Model Context Protocol)", _mcp),
):
    register(_fw)
