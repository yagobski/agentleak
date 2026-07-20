import { useMemo, useState } from "react"
import { ArrowRight, Search } from "lucide-react"
import { Link } from "react-router-dom"
import { SITE_URL, SiteFooter, SiteNav, usePageMeta } from "@/features/SiteChrome"

type Category = "frameworks" | "repositories" | "protocols" | "infrastructure" | "roadmap"

type Integration = {
  name: string
  maker: string
  description: string
  category: Category
  logo: string
  href?: string
  available: boolean
}

const CATEGORY_LABELS: Record<Category, string> = {
  frameworks: "Agent frameworks",
  repositories: "Code & repositories",
  protocols: "Protocols & telemetry",
  infrastructure: "CI & infrastructure",
  roadmap: "Coming soon",
}

const CATEGORY_DESCRIPTIONS: Record<Category, string> = {
  frameworks: "Capture model calls, tools, memory, handoffs and outputs directly from the runtimes your agents already use.",
  repositories: "Put deterministic privacy evidence next to the exact commit, branch and merge gate that can fix it.",
  protocols: "Normalize open protocols and exported spans into AgentLeak’s auditable eight-channel trace model.",
  infrastructure: "Run locally, in containers or in any CI runner without moving sensitive traces to another vendor.",
  roadmap: "Native workflow connectors planned for teams that want findings delivered where they already investigate and ship.",
}

const INTEGRATIONS: Integration[] = [
  { name: "LangChain", maker: "LangChain", description: "Capture tools, model output and agent actions through the AgentLeak callback.", category: "frameworks", logo: "/assets/frameworks/langchain.svg", href: "/docs/integrations#frameworks", available: true },
  { name: "LangGraph", maker: "LangChain", description: "Convert graph state, routed handoffs and node output into one ordered privacy trace.", category: "frameworks", logo: "/assets/frameworks/langgraph.svg", href: "/docs/integrations#frameworks", available: true },
  { name: "CrewAI", maker: "CrewAI", description: "Attach step and task callbacks while preserving which crew and agent handled each value.", category: "frameworks", logo: "/assets/frameworks/crewai.svg", href: "/docs/integrations#frameworks", available: true },
  { name: "Pydantic AI", maker: "Pydantic", description: "Normalize typed message history, tool calls and structured responses for analysis.", category: "frameworks", logo: "/assets/frameworks/pydantic.svg", href: "/docs/integrations#frameworks", available: true },
  { name: "smolagents", maker: "Hugging Face", description: "Ingest agent steps and tool observations without coupling the runtime to the analyzer.", category: "frameworks", logo: "/assets/frameworks/huggingface.svg", href: "/docs/integrations#frameworks", available: true },
  { name: "Google ADK", maker: "Google", description: "Turn ADK event lists and sub-agent routing into trace-linked privacy evidence.", category: "frameworks", logo: "/assets/frameworks/google.svg", href: "/docs/integrations#frameworks", available: true },
  { name: "GitHub Actions", maker: "GitHub", description: "Run AgentLeak on every pull request and block merges when a policy threshold is crossed.", category: "repositories", logo: "/assets/integrations/githubactions.svg", href: "/docs/ci-cd#github", available: true },
  { name: "GitLab CI", maker: "GitLab", description: "Add the same deterministic privacy gate to GitLab pipelines and protected branches.", category: "repositories", logo: "/assets/integrations/gitlab.svg", href: "/docs/ci-cd#gitlab", available: true },
  { name: "Model Context Protocol", maker: "MCP", description: "Capture MCP tool requests, responses and server boundaries as first-class channels.", category: "protocols", logo: "/assets/frameworks/modelcontextprotocol.svg", href: "/docs/integrations#frameworks", available: true },
  { name: "OpenTelemetry", maker: "OpenTelemetry", description: "Translate OTLP and OpenInference spans while retaining source, target and trace order.", category: "protocols", logo: "/assets/frameworks/opentelemetry.svg", href: "/docs/integrations#otel", available: true },
  { name: "Docker", maker: "Docker", description: "Self-host the complete platform or run isolated scans beside your existing services.", category: "infrastructure", logo: "/assets/integrations/docker.svg", href: "/docs/getting-started", available: true },
  { name: "GitHub App", maker: "GitHub", description: "Inline pull-request annotations, repository onboarding and managed status checks.", category: "roadmap", logo: "/assets/integrations/github.svg", available: false },
  { name: "GitLab App", maker: "GitLab", description: "Native merge-request findings and project-level privacy policy management.", category: "roadmap", logo: "/assets/integrations/gitlab.svg", available: false },
  { name: "Sentry", maker: "Sentry", description: "Turn agent privacy findings into trace-linked issues alongside production errors.", category: "roadmap", logo: "/assets/integrations/sentry.svg", available: false },
  { name: "Datadog", maker: "Datadog", description: "Correlate AgentLeak evidence with agent observability, service traces and release events.", category: "roadmap", logo: "/assets/integrations/datadog.svg", available: false },
  { name: "Jira", maker: "Atlassian", description: "Create remediation work with the affected file, channel, trace and policy already attached.", category: "roadmap", logo: "/assets/integrations/jira.svg", available: false },
]

const FILTERS: readonly ({ value: "all"; label: string } | { value: Category; label: string })[] = [
  { value: "all", label: "All integrations" },
  { value: "frameworks", label: "Frameworks" },
  { value: "repositories", label: "Code & repositories" },
  { value: "protocols", label: "Protocols & telemetry" },
  { value: "infrastructure", label: "CI & infrastructure" },
  { value: "roadmap", label: "Coming soon" },
]

function IntegrationCard({ integration }: { integration: Integration }) {
  const card = (
    <>
      <div className="integrations-card-head">
        <span className="integrations-logo"><img src={integration.logo} alt="" width="38" height="38" loading="lazy" decoding="async" /></span>
        <span className={integration.available ? "integrations-status available" : "integrations-status"}>{integration.available ? "Available" : "Coming soon"}</span>
      </div>
      <h3>{integration.name}</h3>
      <p className="integrations-maker">By {integration.maker}</p>
      <p className="integrations-description">{integration.description}</p>
      {integration.href && <span className="integrations-card-link">View setup <ArrowRight aria-hidden="true" /></span>}
    </>
  )
  return integration.href ? <Link className="integrations-card" to={integration.href}>{card}</Link> : <article className="integrations-card integrations-card-muted">{card}</article>
}

export function Integrations() {
  const [filter, setFilter] = useState<"all" | Category>("all")
  const [query, setQuery] = useState("")

  usePageMeta(
    "AgentLeak integrations — frameworks, repositories and telemetry",
    "Connect AgentLeak to LangChain, LangGraph, CrewAI, OpenTelemetry, MCP, GitHub Actions, GitLab CI, Docker and the rest of your agent stack.",
    {
      structuredData: {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        name: "AgentLeak integrations",
        description: "Supported frameworks, repositories, telemetry protocols and CI environments for AgentLeak.",
        url: `${SITE_URL}/integrations`,
        mainEntity: {
          "@type": "ItemList",
          itemListElement: INTEGRATIONS.filter((item) => item.available).map((item, index) => ({
            "@type": "ListItem",
            position: index + 1,
            name: item.name,
          })),
        },
      },
    },
  )

  const groups = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase()
    const items = INTEGRATIONS.filter((item) => {
      if (filter !== "all" && item.category !== filter) return false
      if (!normalized) return true
      return `${item.name} ${item.maker} ${item.description}`.toLocaleLowerCase().includes(normalized)
    })
    return (Object.keys(CATEGORY_LABELS) as Category[])
      .map((category) => ({ category, items: items.filter((item) => item.category === category) }))
      .filter((group) => group.items.length)
  }, [filter, query])

  return (
    <div className="cursor-site integrations-page">
      <SiteNav />
      <main>
        <section className="integrations-hero">
          <p className="cursor-eyebrow">Integrations</p>
          <h1>Connect every part of your agent stack.</h1>
          <p>Capture privacy evidence from the frameworks, protocols, repositories and infrastructure you already use. One normalized trace, without replacing your runtime.</p>
        </section>

        <section className="integrations-directory" aria-labelledby="integrations-directory-title">
          <div className="integrations-directory-head">
            <div>
              <p className="cursor-eyebrow">Directory</p>
              <h2 id="integrations-directory-title">Explore integrations</h2>
            </div>
            <label className="integrations-search">
              <Search aria-hidden="true" />
              <span className="sr-only">Search integrations</span>
              <input value={query} onChange={(event) => setQuery(event.target.value)} type="search" placeholder="Search integrations…" />
            </label>
          </div>
          <div className="integrations-filters" role="group" aria-label="Filter integrations by category">
            {FILTERS.map((item) => <button key={item.value} type="button" data-active={filter === item.value} aria-pressed={filter === item.value} onClick={() => setFilter(item.value)}>{item.label}</button>)}
          </div>

          {groups.length ? groups.map((group) => (
            <section className="integrations-group" key={group.category}>
              <header>
                <h2>{CATEGORY_LABELS[group.category]}</h2>
                <p>{CATEGORY_DESCRIPTIONS[group.category]}</p>
              </header>
              <div className="integrations-grid">
                {group.items.map((integration) => <IntegrationCard key={integration.name} integration={integration} />)}
              </div>
            </section>
          )) : <div className="integrations-empty"><h2>No integration found</h2><p>Try another name or reset the category filter.</p><button type="button" onClick={() => { setQuery(""); setFilter("all") }}>Show all integrations</button></div>}
        </section>

        <section className="integrations-cta">
          <div><p className="cursor-eyebrow">Build your own</p><h2>Any runtime can produce an AgentLeak trace.</h2></div>
          <p>The generic recorder, JSON trace contract and OpenTelemetry ingestion path cover custom frameworks and internal agent platforms.</p>
          <Link to="/docs/integrations">Open integration guides <ArrowRight aria-hidden="true" /></Link>
        </section>
      </main>
      <SiteFooter />
    </div>
  )
}
