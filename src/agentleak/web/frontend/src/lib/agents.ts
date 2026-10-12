// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
// Display labels for agent frameworks. The authoritative list (and the SDK
// connection snippets) come from the backend registry via /api/meta and
// /api/projects/{id}/connect — this is only a fallback for rendering labels.
export const AGENT_LABELS: Record<string, string> = {
  generic: "Generic / SDK",
  langchain: "LangChain",
  langgraph: "LangGraph",
  crewai: "CrewAI",
  autogen: "AutoGen",
  openai_swarm: "OpenAI Swarm / Agents SDK",
  llamaindex: "LlamaIndex",
  semantic_kernel: "Semantic Kernel",
  pydantic_ai: "Pydantic AI",
  smolagents: "smolagents",
  google_adk: "Google ADK",
}

export function agentLabel(t: string): string {
  return AGENT_LABELS[t] ?? t
}
