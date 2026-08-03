import { Link } from "react-router-dom"
import { Arrow } from "@/features/ProductDemos"
import { SITE_URL, SiteFooter, SiteNav, usePageMeta } from "@/features/SiteChrome"
import benchmark from "@/data/benchmark.json"

/**
 * The measured half of the product claim.
 *
 * Everything on this page comes from `scripts/build_benchmark.py`, which runs
 * the analyzer over every bundled scenario and writes `data/benchmark.json`.
 * Nothing is typed in by hand, so the page cannot drift from the numbers, and
 * anyone can re-run the script and get the same figures.
 */

const MODE_LABEL: Record<string, string> = {
  pattern: "By pattern",
  norm: "By norm",
  hijack: "By hijack",
}

const SOURCE_LABEL: Record<string, string> = {
  builtin: "Built-in examples",
  agentleak_bench: "AgentLeak Bench",
  ai4privacy_probes: "PII Probes (ai4privacy)",
  privacylens_ci: "PrivacyLens",
  agentdojo_exfil: "AgentDojo",
}

const pct = (n: number, total: number) => (total ? Math.round((100 * n) / total) : 0)

export function Benchmark() {
  const { corpus, by_source: bySource } = benchmark
  // The headline: how often pattern matching alone calls a real leak clean.
  const hard = bySource.filter((row) => row.leak_mode !== "pattern")
  const hardTotal = hard.reduce((sum, row) => sum + row.scenarios, 0)
  const hardMissed = hard.reduce((sum, row) => sum + row.clean_pass_without_ground_truth, 0)
  const hardUnblocked = hard.reduce((sum, row) => sum + row.would_not_block_a_gate, 0)

  usePageMeta(
    "Internal-channel leakage benchmark · AgentLeak",
    `Measured on ${corpus.scenarios} bundled agent scenarios: where a leak actually travels, and how often pattern-matching detection calls a real leak clean. Reproducible, no model calls. Updated ${benchmark.generated_on}.`,
    {
      type: "article",
      structuredData: {
        "@context": "https://schema.org",
        "@type": "Dataset",
        name: "AgentLeak internal-channel leakage benchmark",
        description: `Per-channel privacy leakage rates and detection-tier coverage measured across ${corpus.scenarios} agent scenarios.`,
        url: `${SITE_URL}/benchmark`,
        license: "https://opensource.org/licenses/MIT",
        creator: { "@type": "Organization", name: "AgentLeak", url: SITE_URL },
        dateModified: benchmark.generated_on,
        isAccessibleForFree: true,
        measurementTechnique: "Deterministic regex-tier analysis with exact ground-truth canary matching",
      },
    },
  )

  return (
    <div className="cursor-site">
      <SiteNav />
      <main>
        <section className="cursor-page">
          <div className="cursor-page-hero">
            <p className="cursor-eyebrow">Benchmark · updated {benchmark.generated_on}</p>
            <h1>Pattern matching calls {pct(hardMissed, hardTotal)}% of real leaks clean.</h1>
            <p>
              Run over the {corpus.scenarios} scenarios that ship inside the package. Every number
              below is produced by a script in the repository, with no model in the loop, so
              re-running it reproduces this page exactly.
            </p>
            <div className="cursor-actions">
              <Link className="cursor-button cursor-button-dark" to="/docs#scenarios">
                How the corpus is built <Arrow />
              </Link>
              <Link className="cursor-button cursor-button-light" to="/research#attribution">
                Sources and licences <Arrow />
              </Link>
            </div>
          </div>

          <div className="cursor-research-stats">
            <div><b>{corpus.scenarios}</b><span>scenarios measured</span></div>
            <div><b>{hardMissed}</b><span>scored a perfect 100/100 by patterns alone</span></div>
            <div><b>{pct(hardUnblocked, hardTotal)}%</b><span>of real leaks would not block a CI gate</span></div>
            <div><b>{corpus.internal_only}</b><span>leaks that never touched the final answer</span></div>
          </div>

          <section className="docs-section">
            <h2>Where a leak actually travels</h2>
            <p style={{ maxWidth: "660px", color: "var(--s-9d9c96)", fontSize: "14px", lineHeight: 1.6 }}>
              Of the {corpus.leaking} scenarios that leak, {corpus.internal_only} leak on internal
              channels only — the final answer stays clean in every one of them. An audit that reads
              the output alone reports those as passing.
            </p>
            <div className="docs-table">
              {corpus.channels.map((row) => (
                <div key={row.channel}>
                  <code>{row.share}%</code>
                  <span>
                    <b>{row.channel}</b> — leaked in {row.scenarios} of {corpus.leaking} leaking
                    scenarios
                  </span>
                </div>
              ))}
            </div>
            <div className="docs-callout">
              <strong>Read this honestly</strong>
              <p>{benchmark.caveat}</p>
            </div>
          </section>

          <section className="docs-section">
            <h2>What the pattern tier misses, per source</h2>
            <p style={{ maxWidth: "660px", color: "var(--s-9d9c96)", fontSize: "14px", lineHeight: 1.6 }}>
              Each scenario is scored twice: once against its ground truth, and once with the regex
              tier alone. The gap is the difference between “no pattern matched” and “nothing
              leaked” — and it is where a privacy score quietly stops being worth anything.
            </p>
            <div className="cursor-attrib-list">
              {bySource.map((row) => (
                <div className="cursor-attrib" key={row.source}>
                  <div>
                    <code>
                      {SOURCE_LABEL[row.source] ?? row.source} · {row.scenarios} scenarios
                    </code>
                    <span>
                      {row.clean_pass_without_ground_truth} scored a perfect 100/100 without ground
                      truth · {row.would_not_block_a_gate} would not block a gate ·{" "}
                      {row.fails_with_ground_truth} fail once it is attached
                    </span>
                  </div>
                  <em>{MODE_LABEL[row.leak_mode] ?? row.leak_mode}</em>
                </div>
              ))}
            </div>
          </section>

          <section className="docs-section">
            <h2>Method, and what this is not</h2>
            <p style={{ maxWidth: "660px", color: "var(--s-9d9c96)", fontSize: "14px", lineHeight: 1.6 }}>
              {benchmark.method}
            </p>
            <div className="docs-table">
              {[
                ["Not a model ranking", "No model is called. This measures detection against fixed traces, so it says nothing about which LLM leaks more. A model-by-model run needs API keys and is a separate exercise."],
                ["Reproducible", `Run ${benchmark.reproduce} against AgentLeak ${benchmark.agentleak_version}. Same inputs, same numbers.`],
                ["Deterministic by design", "Scoring uses exact ground-truth matching, not a judge model, which is what makes a regression in CI meaningful rather than noise."],
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
