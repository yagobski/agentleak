import type { ReactNode } from "react"
import { Link, Navigate, useParams } from "react-router-dom"
import {
  AgentTerminal,
  Arrow,
  CIGateDemo,
  PlatformWorkbench,
  RunReportDemo,
} from "@/features/ProductDemos"
import {
  FAQ_ITEMS,
  FEATURE_PAGES,
  FaqItem,
  REPO_URL,
  SiteFooter,
  SiteNav,
  usePageMeta,
} from "@/features/SiteChrome"

type Section = { title: string; body: string; points: string[] }
type FeatureContent = {
  eyebrow: string
  title: string
  lede: string
  metaTitle: string
  metaDescription: string
  demo: ReactNode
  sections: Section[]
}

// One dedicated, SEO-oriented page per capability. Each reuses the exact same
// live preview shown on the landing page, sized identically to the hero.
const FEATURE_CONTENT: Record<string, FeatureContent> = {
  "trace-analysis": {
    eyebrow: "Complete trace analysis",
    title: "See what your agent exposes on the way to the answer.",
    lede: "AgentLeak replays the whole execution trace and follows every sensitive value through six internal channels. A clean final answer no longer hides a leak in a tool call, shared memory, a log or a generated file.",
    metaTitle: "Trace analysis · AgentLeak",
    metaDescription: "AgentLeak replays the whole agent execution trace across six channels (tools, memory, messages, logs, files, output) and pinpoints every exposure with a severity level and an exact fix.",
    demo: <RunReportDemo />,
    sections: [
      {
        title: "Six channels, one schema",
        body: "Traces from any framework normalize to one AgentLeak schema, so the analysis is identical whatever produced the run.",
        points: ["User input and final output", "Tool calls and tool responses", "Inter-agent messages and shared memory", "Logs and generated files"],
      },
      {
        title: "Severity you can defend",
        body: "Every finding gets a level from L1 to L4 based on how sensitive the exposed value is and where it went, not a vague red/yellow/green badge.",
        points: ["L1 to L4 severity per finding", "The exact channel where exposure happened", "Reconstructed leak path across events", "Canary matching for realistic vaults"],
      },
      {
        title: "A fix, not just a flag",
        body: "Each finding carries a remediation hint: prose for your team and a structured, machine-readable hint an agent can apply on its own.",
        points: ["Ready-to-paste code fixes", "Per-channel redaction advice", "Priority-sorted next steps", "Structured hints for autonomous agents"],
      },
    ],
  },
  agentrisk: {
    eyebrow: "AgentRisk scoring",
    title: "A privacy score your whole team can explain.",
    lede: "AgentRisk is a deterministic, severity-weighted risk index from 0 to 1, defined in a published benchmark. The same trace always yields the same score, so a regression in CI means the agent changed, not the judge.",
    metaTitle: "AgentRisk scoring · AgentLeak",
    metaDescription: "AgentRisk is a deterministic, severity-weighted privacy risk index from 0 to 1 with a readable 0-100 privacy score. Reproducible by design, so CI regressions are real.",
    demo: <PlatformWorkbench />,
    sections: [
      {
        title: "Deterministic by design",
        body: "The score is a closed-form function of the findings and the audited vault. No model decides the number, so it never drifts between runs.",
        points: ["Same trace, same score, every time", "Severity-weighted, normalized 0 to 1", "A readable 0-100 privacy score", "Reproducible in CI and offline"],
      },
      {
        title: "Grounded in the benchmark",
        body: "AgentRisk uses the same channels and severity model as the published AgentLeak benchmark, so results are comparable across agents and versions.",
        points: ["36 scenarios across 4 domains", "Adversary levels A0-A2", "Comparable across agents", "Trend the score over time"],
      },
      {
        title: "Built for regressions",
        body: "Track the score per agent and per release. A rising risk index is an early, quantified warning before anything ships.",
        points: ["Per-agent leaderboard", "Per-release trend line", "Threshold you set per project", "Evidence attached to every run"],
      },
    ],
  },
  "ci-gate": {
    eyebrow: "CI policy gate",
    title: "Make privacy a required check, not an afterthought.",
    lede: "Set a policy per project and wire AgentLeak into CI. When an agent crosses its boundary, the check fails and the pull request is blocked, with the offending channel and severity attached to the run.",
    metaTitle: "CI policy gate · AgentLeak",
    metaDescription: "Wire AgentLeak into GitHub or GitLab as a required status check. A privacy boundary crossing blocks the merge with the trace, channel and severity attached as evidence.",
    demo: <CIGateDemo />,
    sections: [
      {
        title: "One boundary per project",
        body: "Define what counts as a failure (a channel, a severity level, a score threshold) and the gate enforces it on every run.",
        points: ["Fail below a privacy score", "Block a channel above a level", "Per-project, version-controlled policy", "Sensible defaults out of the box"],
      },
      {
        title: "A required status check",
        body: "AgentLeak reports back as a normal CI check on GitHub or GitLab, so a failing privacy gate blocks the merge like any failing test.",
        points: ["GitHub / GitLab status check", "Non-zero exit code from the CLI", "Runs in any shell or Makefile", "No extra infrastructure"],
      },
      {
        title: "Evidence on the PR",
        body: "A blocked merge comes with the trace, the offending channel and the severity, so the author knows exactly what to fix.",
        points: ["Offending channel highlighted", "Severity and risk index shown", "Link straight to the full report", "The exact remediation attached"],
      },
    ],
  },
  "agent-api": {
    eyebrow: "Built for autonomous agents",
    title: "Agents can discover, test and fix themselves.",
    lede: "llms.txt discovery, one-call onboarding, scoped project keys and machine-readable remediation hints. An agent can find AgentLeak, audit itself and fix its own leaks in a bounded loop, with no browser and no human in the middle.",
    metaTitle: "Agent API · AgentLeak",
    metaDescription: "AgentLeak exposes a machine-first API: llms.txt discovery, one-call onboarding, scoped keys and structured remediation hints so autonomous agents can self-test and improve in a loop.",
    demo: <AgentTerminal />,
    sections: [
      {
        title: "Discoverable by machines",
        body: "A machine-readable llms.txt and an A2A agent card let an agent find AgentLeak and learn how to use it without a human.",
        points: ["/llms.txt discovery", "/.well-known/agent-card.json", "OpenAPI at /openapi.json", "One-call onboarding"],
      },
      {
        title: "Self-test in one call",
        body: "An agent submits its own trace and gets back a full report: passed, compliant, failed frameworks and the exact remediation hints.",
        points: ["POST /api/selftest", "Scoped project API keys", "Compliance verdict per framework", "Structured, actionable hints"],
      },
      {
        title: "A bounded improvement loop",
        body: "The improve endpoint returns a delta versus the previous run and priority-sorted next steps, so an agent can converge on a clean score safely.",
        points: ["POST /api/agent/improve", "Delta versus the previous run", "Priority-sorted next steps", "Generous free quota for agents"],
      },
    ],
  },
}

export const FEATURE_SLUGS = Object.keys(FEATURE_CONTENT)

export function FeaturePage() {
  const { slug = "" } = useParams()
  const content = FEATURE_CONTENT[slug]
  usePageMeta(
    content?.metaTitle ?? "Feature · AgentLeak",
    content?.metaDescription ?? "",
  )
  if (!content) return <Navigate to="/" replace />

  return (
    <div className="cursor-site">
      <SiteNav />
      <main>
        <section className="cursor-page">
          <div className="cursor-page-hero">
            <p className="cursor-eyebrow">{content.eyebrow}</p>
            <h1>{content.title}</h1>
            <p>{content.lede}</p>
            <div className="cursor-actions">
              <Link className="cursor-button cursor-button-dark" to="/register">Run your first audit <Arrow /></Link>
              <Link className="cursor-button cursor-button-light" to="/docs">Read the docs <Arrow /></Link>
            </div>
          </div>
        </section>

        <div className="cursor-page-preview">
          <div className="cursor-feature-visual">{content.demo}</div>
        </div>

        <div className="cursor-page-sections">
          {content.sections.map((section) => (
            <article key={section.title}>
              <h3>{section.title}</h3>
              <p>{section.body}</p>
              <ul>{section.points.map((point) => <li key={point}>{point}</li>)}</ul>
            </article>
          ))}
        </div>

        <section className="cursor-related">
          <header><p className="cursor-eyebrow">Explore the platform</p><h2>The rest of the loop.</h2></header>
          <div className="cursor-related-grid">
            {FEATURE_PAGES.filter((page) => page.slug !== slug).map((page) => (
              <Link key={page.slug} to={`/features/${page.slug}`} className="cursor-related-card">
                <b>{page.title}</b>
                <small>{page.blurb}</small>
                <span>Learn more <Arrow /></span>
              </Link>
            ))}
          </div>
        </section>

        <section className="cursor-faq" id="faq">
          <header><p className="cursor-eyebrow">FAQ</p><h2>Questions, answered.</h2></header>
          <div className="cursor-faq-list">
            {FAQ_ITEMS.slice(0, 5).map(([q, a]) => <FaqItem key={q} q={q} a={a} />)}
          </div>
        </section>

        <section className="cursor-final-cta">
          <div className="cursor-final-inner">
            <p className="cursor-eyebrow">Ready when you are</p>
            <h2>Test the path, not only the answer.</h2>
            <p>Create a local workspace, run a bundled scenario, then wire AgentLeak into CI or let your agent onboard itself.</p>
            <div className="cursor-actions">
              <Link className="cursor-button cursor-button-dark" to="/register">Start testing AgentLeak <Arrow /></Link>
              <a className="cursor-button cursor-button-light" href={REPO_URL}>View source <Arrow /></a>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  )
}
