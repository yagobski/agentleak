import { Link, Navigate, useLocation } from "react-router-dom"
import { Arrow } from "@/features/ProductDemos"
import { FeatureDiagramGrid } from "@/features/FeatureDiagramGrid"
import { FEATURE_PAGES, REPO_URL, SITE_URL, SiteFooter, SiteNav, usePageMeta } from "@/features/SiteChrome"

type PageSection = { title: string; body: string; points?: string[] }
type SeoPageContent = {
  eyebrow: string
  title: string
  lede: string
  metaTitle: string
  metaDescription: string
  schemaType: "WebPage" | "AboutPage"
  sections: PageSection[]
  related: { href: string; title: string; body: string }[]
}

const SEO_PAGES: Record<string, SeoPageContent> = {
  "/security": {
    eyebrow: "Security & privacy architecture",
    title: "Privacy testing that keeps evidence inside your boundary.",
    lede: "AgentLeak is local-first, deterministic and redacted by default. Use the open-source analyzer offline, self-host the full platform, or send synthetic traces to the hosted service.",
    metaTitle: "AI Agent Privacy & Security Testing · AgentLeak",
    metaDescription: "Audit AI agent privacy locally across tools, memory, messages, logs and files. Deterministic scoring, redacted evidence, no telemetry and self-hosting.",
    schemaType: "WebPage",
    sections: [
      { title: "Local by default", body: "The core detector and AgentRisk scorer run in-process with regex, dictionaries, entropy and optional Presidio. No account, network call or hosted model is required.", points: ["No telemetry or phone-home", "Raw matches redacted in reports", "Synthetic scenarios for safe validation"] },
      { title: "Trace-linked evidence", body: "Every finding keeps its channel, event and severity context. Reviewers can see where data entered, which agent handled it and where disclosure occurred.", points: ["Eight normalized execution channels", "Leak provenance and topology", "Stable report digests for CI"] },
      { title: "Bounded automation", body: "Projects define a vault, detectors and policy. Autonomous agents receive scoped keys and machine-readable remediation without access to another project’s evidence.", points: ["Per-project credentials", "Bring your own model key", "Explicit quotas and rate limits"] },
    ],
    related: [
      { href: "/docs/privacy-compliance", title: "Compliance evidence", body: "Map findings to seven privacy and security frameworks without claiming certification." },
      { href: "/docs/scoring", title: "AgentRisk scoring", body: "Re-derive every risk score from the report and audited vault." },
      { href: "/features/code-scan", title: "Static code scan", body: "Catch hardcoded credentials and unsafe logging paths before runtime." },
    ],
  },
  "/use-cases/multi-agent-privacy": {
    eyebrow: "Use case · Multi-agent systems",
    title: "Find the leak that happens between agents.",
    lede: "A coordinator can keep its final answer clean while a specialist copies sensitive context into a handoff, shared memory or tool argument. AgentLeak captures that internal path and names the boundary that failed.",
    metaTitle: "Multi-Agent Privacy Testing & Leak Detection · AgentLeak",
    metaDescription: "Detect privacy leaks across AI agent handoffs, shared memory, tool calls and logs. Trace provenance, score AgentRisk and block regressions in CI.",
    schemaType: "WebPage",
    sections: [
      { title: "Capture every handoff", body: "Normalize LangGraph, CrewAI, MCP, OpenTelemetry and generic traces into the same channel model, including inter-agent messages and shared memory.", points: ["Coordinator-to-worker messages", "Delegation and tool arguments", "Memory reads and writes"] },
      { title: "Reconstruct provenance", body: "Group detections by secret, follow each value from its source event to every disclosure and display the agent topology that carried it.", points: ["Source versus disclosure semantics", "Per-secret propagation paths", "Per-channel risk localization"] },
      { title: "Verify the repair", body: "Replay the same scenario after redaction, minimization or access-control changes. Deterministic controls show whether the leak disappeared without changing the test.", points: ["Clean controls for false positives", "Before-and-after report comparison", "CI thresholds per project"] },
    ],
    related: [
      { href: "/features/trace-analysis", title: "Trace analysis", body: "Inspect all eight normalized execution channels." },
      { href: "/docs/integrations", title: "Framework integrations", body: "Instrument LangChain, LangGraph, CrewAI, MCP and OpenTelemetry." },
      { href: "/features/red-team", title: "Adversarial red team", body: "Probe agent handoffs with reproducible privacy attacks." },
    ],
  },
  "/about": {
    eyebrow: "About AgentLeak",
    title: "Open infrastructure for measurable agent privacy.",
    lede: "AgentLeak is the open implementation of research on privacy leakage across AI agent execution traces. It exists because output-only reviews cannot see the channels where agents actually work.",
    metaTitle: "About AgentLeak · Open AI Agent Privacy Research",
    metaDescription: "Learn why AgentLeak was created, how the open-source project relates to published agent privacy research and what its evidence can and cannot prove.",
    schemaType: "AboutPage",
    sections: [
      { title: "The problem", body: "Agent systems move private data through tool calls, memory, messages, logs and files. A polished final answer says nothing about what crossed those internal boundaries.", points: ["Output-only checks miss internal disclosures", "Multi-agent handoffs expand the attack surface", "Black-box scores are hard to audit"] },
      { title: "The approach", body: "Capture the whole trace, detect concrete sensitive values, distinguish sources from disclosures and calculate a severity-weighted score against an explicit vault.", points: ["Evidence before inference", "Closed-form AgentRisk scoring", "Reproducible synthetic controls"] },
      { title: "The boundary", body: "AgentLeak supports engineering and governance reviews; it is not a legal certification. Coverage is limited to the channels a framework emits and the data types detectors recognize.", points: ["False-positive testing is required", "Semantic detection is optional", "Compliance mappings require human review"] },
    ],
    related: [
      { href: "/research", title: "Published research", body: "Read the benchmark, evaluation scope and reproducibility notes." },
      { href: "/security", title: "Security model", body: "Understand local execution, redaction and hosted boundaries." },
      { href: REPO_URL, title: "Open-source repository", body: "Inspect the implementation, tests and public CI history." },
    ],
  },
}

function Breadcrumbs({ current }: { current: string }) {
  return <nav className="seo-breadcrumbs" aria-label="Breadcrumb"><Link to="/">Home</Link><span>/</span><span>{current}</span></nav>
}

function RelatedCards({ items }: { items: SeoPageContent["related"] }) {
  return (
    <section className="cursor-related seo-related">
      <header><p className="cursor-eyebrow">Continue exploring</p><h2>From explanation to implementation.</h2></header>
      <div className="cursor-related-grid">
        {items.map((item) => {
          const content = <><b>{item.title}</b><small>{item.body}</small><span>Open resource <Arrow /></span></>
          return item.href.startsWith("http")
            ? <a className="cursor-related-card" href={item.href} key={item.href}>{content}</a>
            : <Link className="cursor-related-card" to={item.href} key={item.href}>{content}</Link>
        })}
      </div>
    </section>
  )
}

export function FeaturesHub() {
  usePageMeta(
    "AI Agent Privacy Testing Features · AgentLeak",
    "Explore trace analysis, AgentRisk scoring, static code scanning, adversarial red teaming, CI privacy gates and the autonomous Agent API.",
    { structuredData: { "@context": "https://schema.org", "@type": "CollectionPage", name: "AgentLeak features", url: `${SITE_URL}/features` } },
  )
  return <div className="cursor-site"><SiteNav /><main>
    <section className="cursor-page seo-page-hero"><div className="cursor-page-hero"><Breadcrumbs current="Features" /><p className="cursor-eyebrow">Product overview</p><h1>One privacy loop, from raw trace to verified fix.</h1><p>Capture what an agent did, detect what crossed a boundary, explain the score and enforce the repair in CI.</p><div className="cursor-actions"><Link className="cursor-button cursor-button-dark" to="/register">Create a workspace <Arrow /></Link><Link className="cursor-button cursor-button-light" to="/docs/getting-started">Run the quickstart <Arrow /></Link></div></div></section>
    <section className="feature-hub-grid">
      {FEATURE_PAGES.map((page, index) => <Link to={`/features/${page.slug}`} key={page.slug}><span>{String(index + 1).padStart(2, "0")}</span><h2>{page.title}</h2><p>{page.blurb}. See the evidence, operating model and implementation path for this part of AgentLeak.</p><b>Explore feature <Arrow /></b></Link>)}
    </section>
    <RelatedCards items={[{ href: "/security", title: "Security architecture", body: "See where evidence runs, what is stored and how projects are isolated." }, { href: "/use-cases/multi-agent-privacy", title: "Multi-agent privacy", body: "Trace disclosures across coordinators, specialists, memory and tools." }, { href: "/docs", title: "Complete documentation", body: "Install, instrument, score, red-team and enforce AgentLeak." }]} />
  </main><SiteFooter /></div>
}

export function SeoPage() {
  const { pathname } = useLocation()
  const content = SEO_PAGES[pathname]
  usePageMeta(
    content?.metaTitle ?? "AgentLeak",
    content?.metaDescription ?? "",
    content ? { structuredData: { "@context": "https://schema.org", "@type": content.schemaType, name: content.title, description: content.metaDescription, url: `${SITE_URL}${pathname}`, isPartOf: { "@type": "WebSite", name: "AgentLeak", url: SITE_URL } } } : {},
  )
  if (!content) return <Navigate to="/" replace />
  return <div className="cursor-site"><SiteNav /><main>
    <section className="cursor-page seo-page-hero"><div className="cursor-page-hero"><Breadcrumbs current={content.eyebrow.replace(/^.*·\s*/, "")} /><p className="cursor-eyebrow">{content.eyebrow}</p><h1>{content.title}</h1><p>{content.lede}</p><div className="cursor-actions"><Link className="cursor-button cursor-button-dark" to="/register">Create a workspace <Arrow /></Link><Link className="cursor-button cursor-button-light" to="/docs/getting-started">Read the quickstart <Arrow /></Link></div></div></section>
    {pathname === "/use-cases/multi-agent-privacy" && <FeatureDiagramGrid slug="multi-agent-privacy" eyebrow="The multi-agent control loop" heading="Make every handoff inspectable." />}
    <div className="cursor-page-sections seo-page-sections">{content.sections.map((section) => <article key={section.title}><h2>{section.title}</h2><p>{section.body}</p>{section.points && <ul>{section.points.map((point) => <li key={point}>{point}</li>)}</ul>}</article>)}</div>
    <RelatedCards items={content.related} />
  </main><SiteFooter /></div>
}
