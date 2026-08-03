import { Link } from "react-router-dom"
import { Arrow } from "@/features/ProductDemos"
import { SITE_URL, SiteFooter, SiteNav, usePageMeta } from "@/features/SiteChrome"

/**
 * The AI Act page.
 *
 * Written to survive a lawyer reading it. Every date and figure below is from
 * Regulation (EU) 2024/1689 itself, the penalty tiers are kept distinct
 * (they are routinely conflated), and the page says plainly that a mapping is
 * not a certification. Overstating here would be the fastest way to lose the
 * buyer this page exists to reach.
 */

const TIMELINE: readonly (readonly [string, string, boolean])[] = [
  ["2 Feb 2025", "Prohibited practices (Art. 5) and AI-literacy duties apply.", false],
  ["2 Aug 2025", "General-purpose AI model obligations, governance and penalties apply.", false],
  ["2 Aug 2026", "General application — including the Annex III high-risk obligations.", true],
  ["2 Aug 2027", "High-risk AI that is a safety component of a regulated product (Annex I).", false],
]

const ARTICLES: readonly (readonly [string, string, string])[] = [
  [
    "Art. 9 — Risk management",
    "A continuous, documented process across the lifecycle, with testing against reasonably foreseeable misuse.",
    "Every run is a dated, reproducible test with a deterministic score, so the process leaves an artefact instead of a claim.",
  ],
  [
    "Art. 15 — Accuracy, robustness, cybersecurity",
    "Resilience against third parties altering use or behaviour by exploiting vulnerabilities; explicitly names adversarial examples and model evasion.",
    "100 prompt-injection exfiltration scenarios and 46 attack classes, run as a suite rather than ad hoc.",
  ],
  [
    "Art. 12 — Record-keeping",
    "Automatic logging over the system's lifetime, to a degree appropriate to its purpose.",
    "Traces are the record. JSON reports carry findings, channels, severity and a digest.",
  ],
  [
    "Art. 11 + Annex IV — Technical documentation",
    "Documentation sufficient to show the system meets the requirements.",
    "Exportable JSON, HTML and Markdown reports with the finding-to-control evidence matrix.",
  ],
  [
    "Art. 26 — Deployer obligations",
    "Deployers must monitor operation and keep logs under their control.",
    "The gate runs in your CI on your machine; nothing leaves the boundary unless you send it.",
  ],
]

export function Compliance() {
  usePageMeta(
    "EU AI Act evidence for agent systems · AgentLeak",
    "Annex III high-risk obligations apply from 2 August 2026. Produce dated, reproducible evidence that an agent system was tested against prompt injection and data leakage — across tool calls, memory and logs, not just the final answer. Mapped to the AI Act, ISO/IEC 42001, NIST AI RMF and the OWASP LLM Top 10.",
    {
      type: "article",
      structuredData: {
        "@context": "https://schema.org",
        "@type": "Article",
        headline: "EU AI Act evidence for agent systems",
        description:
          "How a deterministic, channel-aware privacy report maps to Articles 9, 11, 12, 15 and 26 of Regulation (EU) 2024/1689.",
        url: `${SITE_URL}/compliance/eu-ai-act`,
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
            <p className="cursor-eyebrow">Compliance · EU AI Act</p>
            <h1>The obligations landed on 2 August 2026. Evidence is the deliverable.</h1>
            <p>
              For Annex III high-risk systems, testing against prompt injection and data leakage is
              no longer a good practice you can describe in a policy document — it is a requirement
              you have to be able to show you met. An agent makes that harder than a model does,
              because the leak usually happens on a channel nobody exports: a tool call, a shared
              memory write, a log line. AgentLeak produces that evidence as a file.
            </p>
            <div className="cursor-actions">
              <Link className="cursor-button cursor-button-dark" to="/docs/privacy-compliance">
                See the mapping <Arrow />
              </Link>
              <Link className="cursor-button cursor-button-light" to="/benchmark">
                What output-only testing misses <Arrow />
              </Link>
            </div>
          </div>

          <section className="docs-section">
            <h2>Where we are in the calendar</h2>
            <div className="docs-table">
              {TIMELINE.map(([date, what, now]) => (
                <div key={date}>
                  <code>{date}</code>
                  <span>
                    {what} {now && <b style={{ color: "#ff8257" }}>← in force now</b>}
                  </span>
                </div>
              ))}
            </div>
            <div className="docs-callout">
              <strong>Get the penalty tiers right</strong>
              <p>
                The headline €35M / 7% of worldwide annual turnover applies to the{" "}
                <b>prohibited practices</b> in Article 5. Failing the high-risk requirements —
                including the risk-management and robustness duties this page is about — sits in the
                next tier: up to €15M or 3% of worldwide annual turnover, whichever is higher
                (Art. 99). Supplying incorrect or misleading information to authorities is up to
                €7.5M or 1%. Both tiers are large enough to matter; quoting the wrong one at a
                procurement meeting is not.
              </p>
            </div>
          </section>

          <section className="docs-section">
            <h2>Article by article</h2>
            <p style={{ maxWidth: "660px", color: "var(--s-9d9c96)", fontSize: "14px", lineHeight: 1.6 }}>
              What the regulation asks for, and the artefact that answers it.
            </p>
            <div className="cursor-attrib-list">
              {ARTICLES.map(([article, requirement, answer]) => (
                <div className="cursor-attrib" key={article} style={{ alignItems: "flex-start" }}>
                  <div>
                    <code>{article}</code>
                    <span>{requirement}</span>
                    <span style={{ color: "var(--s-c9c8c1)" }}>{answer}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="docs-section">
            <h2>One report, four frameworks</h2>
            <p style={{ maxWidth: "660px", color: "var(--s-9d9c96)", fontSize: "14px", lineHeight: 1.6 }}>
              Findings carry their control mappings, so the same run answers an AI Act file, an ISO
              audit and a security review without being re-run or re-formatted.
            </p>
            <div className="docs-table">
              {[
                ["EU AI Act", "Arts. 9, 11, 12, 15 and 26, plus Annex IV technical documentation."],
                ["ISO/IEC 42001", "AI management system: operational controls and the evidence that they ran."],
                ["NIST AI RMF", "MEASURE — documented, repeated testing with a metric that does not move on its own."],
                ["OWASP LLM Top 10", "LLM01 prompt injection, LLM02 sensitive information disclosure, LLM06 excessive agency."],
                ["Also mapped", "GDPR (incl. arts. 5, 9, 25, 32), HIPAA, PCI DSS v4.0, Quebec Law 25 and 7 more."],
              ].map(([n, body]) => (
                <div key={n}>
                  <code>{n}</code>
                  <span>{body}</span>
                </div>
              ))}
            </div>
            <div className="docs-callout">
              <strong>A mapping is not a certification</strong>
              <p>
                This is tooling to make a review faster and better evidenced, not legal advice and
                not a conformity assessment. No report from any tool makes a system compliant; a
                notified body, your own risk assessment and your documentation do. What we remove is
                the part where you cannot show what you tested.
              </p>
            </div>
          </section>

          <section className="docs-section">
            <h2>Who this is for</h2>
            <p style={{ maxWidth: "660px", color: "var(--s-9d9c96)", fontSize: "14px", lineHeight: 1.6 }}>
              The bundled corpus covers healthcare, finance, legal and corporate operations — which
              is not a coincidence. Annex III high-risk categories cluster in exactly those places:
              access to essential private services and creditworthiness, employment and worker
              management, education, and administration of justice.
            </p>
          </section>
        </section>
        <SiteFooter />
      </main>
    </div>
  )
}
