import { Link } from "react-router-dom"
import { Arrow } from "@/features/ProductDemos"
import { SITE_URL, SiteFooter, SiteNav, usePageMeta } from "@/features/SiteChrome"

/**
 * An honest comparison, written to be useful to someone who has not decided yet.
 *
 * The neighbours here are good tools solving a different problem, and saying so
 * plainly is what makes the distinction credible. Anyone evaluating us is going
 * to run promptfoo anyway; the useful claim is that the two answer different
 * questions, not that one wins.
 */

const TOOLS = [
  {
    name: "promptfoo",
    what: "Prompt and model evaluation, plus a red-team suite. Declarative YAML, strong developer ergonomics, large plugin catalog.",
    scope: "Model input/output",
    verdict: "Use it for evals and adversarial prompts. It grades the answer; it does not model a run as channels.",
  },
  {
    name: "Garak",
    what: "LLM vulnerability scanner with a wide probe library — jailbreaks, toxicity, leakage of training data.",
    scope: "Model behaviour",
    verdict: "Use it to probe a model. Its unit is a prompt/response pair, not an agent trajectory with tools and memory.",
  },
  {
    name: "PyRIT",
    what: "Microsoft's risk identification toolkit: orchestrators, converters and scorers for automated adversarial testing.",
    scope: "Model behaviour, orchestrated",
    verdict: "Use it to build attack campaigns. Scoring is model-graded, so a number moves when the judge does.",
  },
  {
    name: "AgentLeak",
    what: "Privacy forensics over an agent run: eight channels, severity levels, a deterministic score and a CI gate.",
    scope: "The whole system",
    verdict: "Use it to answer whether private data left the boundary, on any channel, with evidence you can attach to an audit.",
    self: true,
  },
]

const ROWS: readonly (readonly [string, string, string, string, string])[] = [
  ["Unit of analysis", "Prompt / response", "Prompt / response", "Prompt / response", "A full run, 8 channels"],
  ["Sees tool calls, memory, logs", "No", "No", "No", "Yes — that is the point"],
  ["Deterministic score", "Assertion-based", "Probe hit rate", "Model-graded", "Yes, 0–1 AgentRisk"],
  ["Ground-truth canaries", "No", "Partial", "No", "Yes, exact match"],
  ["Compliance mapping", "No", "No", "No", "14 frameworks per finding"],
  ["Runs with no API key", "Partly", "Partly", "No", "Yes, fully"],
  ["Adversarial prompt library", "Large", "Large", "Large", "46 classes — smaller"],
  ["Model benchmarking", "Yes", "Yes", "Yes", "No, out of scope"],
]

export function Compare() {
  usePageMeta(
    "AgentLeak vs promptfoo vs Garak vs PyRIT",
    "An honest comparison: promptfoo, Garak and PyRIT test the model's answers. AgentLeak tests the system — tool calls, shared memory, logs and generated files — with a deterministic privacy score and a compliance-mapped report.",
    {
      type: "article",
      structuredData: {
        "@context": "https://schema.org",
        "@type": "Article",
        headline: "AgentLeak vs promptfoo vs Garak vs PyRIT",
        description: "How agent privacy forensics differs from prompt-level model evaluation and red-teaming.",
        url: `${SITE_URL}/compare`,
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
            <p className="cursor-eyebrow">Comparison</p>
            <h1>They test the model. We test the system.</h1>
            <p>
              promptfoo, Garak and PyRIT are good tools, and if you are red-teaming a model you
              should be using one of them. They share an assumption: the thing under test is a
              prompt and the answer that comes back. An agent is not that. It calls tools, writes to
              memory, hands off to other agents and emits logs — and a private value can leave
              through any of those while the answer stays perfectly clean.
            </p>
            <div className="cursor-actions">
              <Link className="cursor-button cursor-button-dark" to="/benchmark">
                See the measured gap <Arrow />
              </Link>
              <Link className="cursor-button cursor-button-light" to="/docs/getting-started">
                Try it in 60 seconds <Arrow />
              </Link>
            </div>
          </div>

          <div className="cursor-attrib-list">
            {TOOLS.map((tool) => (
              <div className="cursor-attrib" key={tool.name}>
                <div>
                  <code>{tool.name}</code>
                  <span>
                    {tool.what} <b style={{ color: "var(--s-c9c8c1)" }}>{tool.verdict}</b>
                  </span>
                </div>
                <em>{tool.scope}</em>
              </div>
            ))}
          </div>

          <section className="docs-section">
            <h2>Side by side</h2>
            <div className="docs-table docs-table-compare">
              <div className="docs-compare-head">
                <span />
                <span>promptfoo</span>
                <span>Garak</span>
                <span>PyRIT</span>
                <span>AgentLeak</span>
              </div>
              {ROWS.map(([label, a, b, c, d]) => (
                <div className="docs-compare-row" key={label}>
                  <span>{label}</span>
                  <span>{a}</span>
                  <span>{b}</span>
                  <span>{c}</span>
                  <span data-self="true">{d}</span>
                </div>
              ))}
            </div>
            <p style={{ maxWidth: "660px", marginTop: "18px", color: "var(--s-9d9c96)", fontSize: "14px", lineHeight: 1.6 }}>
              Note the last two rows. Their prompt libraries are larger than ours and their model
              benchmarking is a real feature we do not have. If you need to know which model
              jailbreaks more easily, use them — not us.
            </p>
          </section>

          <section className="docs-section">
            <h2>Use both</h2>
            <p style={{ maxWidth: "660px", color: "var(--s-9d9c96)", fontSize: "14px", lineHeight: 1.6 }}>
              The natural pipeline runs a model evaluation on the prompts and an AgentLeak gate on
              the run. AgentLeak already imports Promptfoo-compatible plugin IDs, so a red-team
              catalog you have written translates over, and it ingests OpenTelemetry, so a trace
              your observability stack already captures can be scored without new instrumentation.
            </p>
            <div className="docs-table">
              {[
                ["Model layer", "promptfoo, Garak or PyRIT: does the model refuse what it should?"],
                ["System layer", "AgentLeak: did private data cross the boundary on any channel, and can you prove it did not?"],
                ["The gate", "One required status check per layer. They answer different questions, so they fail on different bugs."],
              ].map(([n, body]) => (
                <div key={n}>
                  <code>{n}</code>
                  <span>{body}</span>
                </div>
              ))}
            </div>
          </section>
        </section>
        <SiteFooter />
      </main>
    </div>
  )
}
