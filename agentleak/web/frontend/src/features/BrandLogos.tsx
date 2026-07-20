interface Logo { name: string; src: string }

// Official Simple Icons SVG assets, stored locally so the compatibility strip
// never depends on a third-party request at runtime.
export const ECOSYSTEM_LOGOS: Logo[] = [
  { name: "LangChain", src: "/assets/frameworks/langchain.svg" },
  { name: "LangGraph", src: "/assets/frameworks/langgraph.svg" },
  { name: "CrewAI", src: "/assets/frameworks/crewai.svg" },
  { name: "Pydantic AI", src: "/assets/frameworks/pydantic.svg" },
  { name: "smolagents", src: "/assets/frameworks/huggingface.svg" },
  { name: "Google ADK", src: "/assets/frameworks/google.svg" },
  { name: "OpenTelemetry", src: "/assets/frameworks/opentelemetry.svg" },
  { name: "MCP", src: "/assets/frameworks/modelcontextprotocol.svg" },
]

export function BrandLogo({ logo }: { logo: Logo }) {
  return <img src={logo.src} alt="" width="30" height="30" className="cursor-logo-svg" loading="lazy" decoding="async" />
}
