import { Link } from "react-router-dom"
import { Arrow, PlatformWorkbench } from "@/features/ProductDemos"
import { PAPER_URL, REPO_URL, SITE_URL, SiteFooter, SiteNav, usePageMeta } from "@/features/SiteChrome"

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
      "The primary benchmark. Defines the 8-channel trace model, the L1 to L4 severity levels and the AgentRisk score, evaluated across 36 scenarios in healthcare, finance, legal and corporate domains at adversary levels A0-A2. This tool is the open implementation of that work.",
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
    id: "PrivacyLens",
    kind: "External dataset",
    year: "2024",
    title: "PrivacyLens: contextual integrity, where the leak is a fact and not a pattern",
    summary:
      "Shao et al., NeurIPS 2024 Datasets & Benchmarks. An agent pulls private context in through its tools, then acts toward a recipient the norm says must not receive it. 120 of these scenarios ship with AgentLeak, each carrying the dataset's own sensitive_info_items as exact ground truth — because measured on that pack, a pattern-matching tier alone scores most of them a clean 100 out of 100.",
    href: "https://huggingface.co/datasets/SALT-NLP/PrivacyLens",
    cta: "See the dataset (CC-BY-4.0)",
  },
  {
    id: "AgentDojo",
    kind: "External dataset",
    year: "2024",
    title: "AgentDojo: prompt injection that turns an agent's own tools into the leak path",
    summary:
      "Debenedetti et al., NeurIPS 2024 Datasets & Benchmarks. A legitimate user task, a planted instruction in data the agent was right to read, and an exfiltration that follows through the agent's own legitimate tools while the user-facing answer stays clean. 100 of these ship with AgentLeak, replayed against the upstream environment and carrying the exact stolen values.",
    href: "https://github.com/ethz-spylab/agentdojo",
    cta: "See the dataset (MIT)",
  },
  {
    id: "Compliance",
    kind: "Compliance mapping",
    year: "2026",
    title: "From severity level to legal obligation: GDPR, Law 25, HIPAA, the OWASP LLM Top 10 and more",
    summary:
      "Every finding is tied to one of 7 mapped frameworks (GDPR, Quebec Law 25, NIST AI RMF, the OWASP LLM Top 10, the EU AI Act, HIPAA and PCI-DSS v4.0), not a generic red/yellow/green badge, so a compliance review can trace a score straight back to the clause it maps to. This is a mapping to help a review, not a certification.",
    href: "/docs/api",
    cta: "See the compliance docs",
  },
]

const RESEARCH_STATS: readonly [string, string][] = [
  ["8", "channels per trace"],
  ["4", "severity levels, L1 to L4"],
  ["283", "scenarios bundled"],
  ["3", "research datasets behind them"],
  ["3", "adversary levels, A0 to A2"],
] as const

// Licence terms travel with the data. CC-BY-4.0 in particular obliges us to
// credit the authors wherever their work appears, including here.
const ATTRIBUTIONS: readonly { pack: string; source: string; licence: string; href: string }[] = [
  {
    pack: "privacylens_ci · 120 scenarios",
    source: "PrivacyLens — Shao et al., NeurIPS 2024 Datasets & Benchmarks",
    licence: "CC-BY-4.0",
    href: "https://huggingface.co/datasets/SALT-NLP/PrivacyLens",
  },
  {
    pack: "agentdojo_exfil · 100 scenarios",
    source: "AgentDojo — Debenedetti et al., NeurIPS 2024 Datasets & Benchmarks",
    licence: "MIT",
    href: "https://github.com/ethz-spylab/agentdojo",
  },
  {
    pack: "ai4privacy_probes · 17 scenarios",
    source: "ai4privacy/pii-masking-200k",
    licence: "Open dataset",
    href: "https://huggingface.co/datasets/ai4privacy/pii-masking-200k",
  },
] as const

const CITATION = "@misc{agentleak2026,\n  title  = {AgentLeak: measuring privacy leakage across agent execution traces},\n  author = {AgentLeak},\n  year   = {2026},\n  eprint = {2602.11510},\n  url    = {https://arxiv.org/abs/2602.11510}\n}"

export function Research() {
  usePageMeta(
    "Research · AgentLeak",
    "The published benchmark and methodology behind AgentLeak and AgentRisk: the 8-channel trace model, L1 to L4 severity levels and the deterministic privacy risk index.",
    {
      type: "article",
      structuredData: {
        "@context": "https://schema.org",
        "@type": "ScholarlyArticle",
        headline: "AgentLeak: measuring privacy leakage across agent execution traces",
        description: "The benchmark and methodology behind the 8-channel AgentLeak model and deterministic AgentRisk privacy score.",
        url: `${SITE_URL}/research`,
        sameAs: PAPER_URL,
        datePublished: "2026",
        author: { "@type": "Organization", name: "AgentLeak", url: SITE_URL },
      },
    },
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

        <section className="docs-section cursor-page-howto" id="attribution">
          <header>
            <p className="cursor-eyebrow">Credit where it is due</p>
            <h2>The datasets behind the bundled scenarios.</h2>
          </header>
          <p style={{ maxWidth: "640px", color: "var(--s-9d9c96)", fontSize: "14px", lineHeight: 1.6 }}>
            Three of the four scenario packs are derived from public research datasets. We ship
            them reshaped into AgentLeak traces, but the scenarios, the private facts and the
            attack goals are their authors&rsquo; work. Each pack carries its source, licence and
            attribution in the package itself, and the build scripts that produced them are in the
            repository so the derivation can be checked line by line.
          </p>
          <div className="cursor-attrib-list">
            {ATTRIBUTIONS.map((item) => (
              <a key={item.pack} className="cursor-attrib" href={item.href}>
                <div>
                  <code>{item.pack}</code>
                  <span>{item.source}</span>
                </div>
                <em>{item.licence}</em>
              </a>
            ))}
          </div>
        </section>

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
            <h2>Run the benchmark model against your own agent.</h2>
            <p>The same domains, severity levels and AgentRisk scoring method from the paper are available in the open-source tool. It ships 283 scenarios in total: 10 hand-authored examples (5 with an injected leak, 5 clean controls) plus the full 36-scenario benchmark and two peer-reviewed datasets, all bundled in the package rather than downloaded separately.</p>
            <div className="cursor-actions">
              <Link className="cursor-button cursor-button-dark" to="/register">Create a workspace <Arrow /></Link>
              <Link className="cursor-button cursor-button-light" to="/docs/agents">Agents: discover and onboard <Arrow /></Link>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  )
}
