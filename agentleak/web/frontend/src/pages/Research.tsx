import { Link } from "react-router-dom"
import { Arrow, PlatformWorkbench } from "@/features/ProductDemos"
import { PAPER_URL, REPO_URL, SiteFooter, SiteNav, usePageMeta } from "@/features/SiteChrome"

function Code({ children }: { children: string }) {
  return (
    <pre className="docs-code">
      <code>{children}</code>
    </pre>
  )
}

type Publication = {
  id: string
  kind: string
  year: string
  title: string
  summary: string
  href: string
  cta: string
}

// The publications behind AgentLeak and AgentRisk. The primary benchmark is
// the anchor; the rest document the method the open implementation follows.
const PUBLICATIONS: Publication[] = [
  {
    id: "arXiv:2602.11510",
    kind: "Benchmark",
    year: "2026",
    title: "AgentLeak: measuring privacy leakage across agent execution traces",
    summary:
      "The primary benchmark. Defines the six-channel trace model, the L1 to L4 severity levels and the AgentRisk score, evaluated across 36 scenarios in healthcare, finance, legal and corporate domains at adversary levels A0-A2. This tool is the open implementation of that work.",
    href: PAPER_URL,
    cta: "Read on arXiv",
  },
  {
    id: "Method",
    kind: "Methodology",
    year: "2026",
    title: "AgentRisk: a deterministic, severity-weighted privacy risk index",
    summary:
      "The scoring method in full: how findings map to severity, how the vault normalizes the index, and why the score is reproducible. The same trace always yields the same AgentRisk, which is what makes a CI regression meaningful.",
    href: "/docs/api",
    cta: "See the scoring docs",
  },
  {
    id: "Threat model",
    kind: "Threat model",
    year: "2026",
    title: "Adversarial channels: prompt injection and exfiltration across a run",
    summary:
      "The attack families the red-team module replays (prompt injection, tool-response poisoning, memory and hand-off exfiltration) and how each maps to an internal channel and a severity level.",
    href: "/docs/agents",
    cta: "Read the threat model",
  },
  {
    id: "Dataset",
    kind: "Dataset",
    year: "2026",
    title: "36 scenarios, 4 domains: the benchmark's synthetic data",
    summary:
      "Every scenario ships with a realistic but fully synthetic vault of PII and PHI, canary values that can only appear if the agent actually leaked them, and adversary levels from a passive A0 to an actively adversarial A2 across healthcare, finance, legal and corporate domains.",
    href: "/docs/agents",
    cta: "See the scenario catalog",
  },
  {
    id: "Compliance",
    kind: "Compliance mapping",
    year: "2026",
    title: "From severity level to legal obligation: GDPR, Law 25, HIPAA and the OWASP LLM Top 10",
    summary:
      "Every finding is tied to the regulatory or standards obligation it touches, not a generic red/yellow/green badge, so a compliance review can trace a score straight back to the clause it maps to.",
    href: "/docs/api",
    cta: "See the compliance docs",
  },
]

const RESEARCH_STATS: readonly [string, string][] = [
  ["6", "channels per trace"],
  ["4", "severity levels, L1 to L4"],
  ["36", "benchmark scenarios"],
  ["4", "domains covered"],
  ["3", "adversary levels, A0 to A2"],
] as const

const CITATION = "@misc{agentleak2026,\n  title  = {AgentLeak: measuring privacy leakage across agent execution traces},\n  author = {AgentLeak},\n  year   = {2026},\n  eprint = {2602.11510},\n  url    = {https://arxiv.org/abs/2602.11510}\n}"

export function Research() {
  usePageMeta(
    "Research · AgentLeak",
    "The published benchmark and methodology behind AgentLeak and AgentRisk: the six-channel trace model, L1 to L4 severity levels and the deterministic privacy risk index.",
  )
  return (
    <div className="cursor-site">
      <SiteNav />
      <main>
        <section className="cursor-page">
          <div className="cursor-page-hero">
            <p className="cursor-eyebrow">Research</p>
            <h1>AgentLeak and AgentRisk are not marketing terms.</h1>
            <p>
              The framework and its scoring method come from a published benchmark of privacy
              leakage across agent execution traces. This tool is the open implementation of that
              work: the same channels, the same severity model, the same AgentRisk score.
            </p>
            <div className="cursor-actions">
              <a className="cursor-button cursor-button-dark" href={PAPER_URL}>Read the benchmark <Arrow /></a>
              <a className="cursor-button cursor-button-light" href={REPO_URL}>View the source <Arrow /></a>
            </div>
          </div>

          <div className="cursor-research-stats">
            {RESEARCH_STATS.map(([value, label]) => (
              <div key={label}><b>{value}</b><span>{label}</span></div>
            ))}
          </div>

          <div className="cursor-pubs">
            {PUBLICATIONS.map((pub) => {
              const external = pub.href.startsWith("http")
              const inner = (
                <>
                  <div className="cursor-pub-meta">
                    <span>{pub.id}</span>
                    <em>{pub.kind}</em>
                    <em>{pub.year}</em>
                  </div>
                  <h3>{pub.title}</h3>
                  <p>{pub.summary}</p>
                  <b>{pub.cta} <Arrow /></b>
                </>
              )
              return external ? (
                <a key={pub.id} className="cursor-pub" href={pub.href}>{inner}</a>
              ) : (
                <Link key={pub.id} className="cursor-pub" to={pub.href}>{inner}</Link>
              )
            })}
          </div>
        </section>

        <div className="cursor-page-preview">
          <div className="cursor-feature-visual"><PlatformWorkbench /></div>
        </div>

        <section className="docs-section cursor-page-howto">
          <header><p className="cursor-eyebrow">Cite this work</p><h2>Referencing AgentLeak or AgentRisk in your own research?</h2></header>
          <p style={{ maxWidth: "640px", color: "var(--s-9d9c96)", fontSize: "14px", lineHeight: 1.6 }}>
            Use the BibTeX entry below for the primary benchmark. The methodology and threat-model
            write-ups above are companion documents to the same paper, not separate citations.
          </p>
          <div className="cursor-page-snippet">
            <Code>{CITATION}</Code>
          </div>
        </section>

        <section className="cursor-final-cta">
          <div className="cursor-final-inner">
            <p className="cursor-eyebrow">From paper to practice</p>
            <h2>Run the benchmark against your own agent.</h2>
            <p>Every scenario, severity level and score in the paper ships in the open-source tool. Reproduce the benchmark locally, then point it at your agent.</p>
            <div className="cursor-actions">
              <Link className="cursor-button cursor-button-dark" to="/register">Start testing AgentLeak <Arrow /></Link>
              <Link className="cursor-button cursor-button-light" to="/docs">Read the documentation <Arrow /></Link>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  )
}
