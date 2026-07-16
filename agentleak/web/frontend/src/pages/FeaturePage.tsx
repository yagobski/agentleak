import type { ReactNode } from "react"
import { Link, Navigate, useParams } from "react-router-dom"
import {
  AgentLoopDemo,
  Arrow,
  PipelineGateDemo,
  RiskModelDemo,
  TraceExplorerDemo,
} from "@/features/ProductDemos"
import {
  FAQ_ITEMS,
  FEATURE_PAGES,
  FaqItem,
  SiteFooter,
  SiteNav,
  usePageMeta,
} from "@/features/SiteChrome"

type Section = { title: string; body: string; points: string[] }
type Step = { title: string; body: string }
type Concept = { title: string; body: string; before: string; after: string; principles: string[] }
type FeatureContent = {
  eyebrow: string
  title: string
  lede: string
  metaTitle: string
  metaDescription: string
  demo: ReactNode
  sections: Section[]
  concept: Concept
  steps: Step[]
  snippetLabel: string
  snippet: string
}

function Code({ children }: { children: string }) {
  return (
    <pre className="docs-code">
      <code>{children}</code>
    </pre>
  )
}

// One dedicated, SEO-oriented page per capability. Each reuses the exact same
// live preview shown on the landing page, sized identically to the hero.
const FEATURE_CONTENT: Record<string, FeatureContent> = {
  "trace-analysis": {
    eyebrow: "Complete trace analysis",
    title: "See what your agent exposes on the way to the answer.",
    lede: "AgentLeak replays the whole execution trace and follows every sensitive value through 8 normalized channels. A clean final answer no longer hides a leak in a tool call, shared memory, a log or a generated file.",
    metaTitle: "Trace analysis · AgentLeak",
    metaDescription: "AgentLeak replays the whole agent execution trace across 8 normalized channels (user input, tool calls, tool responses, inter-agent messages, shared memory, logs, generated files, final output) and pinpoints every exposure with a severity level and an exact fix.",
    demo: <TraceExplorerDemo />,
    sections: [
      {
        title: "8 channels, one schema",
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
    concept: {
      title: "An agent run is a dataflow graph, not a chat transcript.",
      body: "A final answer is only one exit from the system. Sensitive data can enter through a tool response, move through memory, cross an agent hand-off and reach a third party without ever appearing in the answer. AgentLeak treats every event as an edge in that flow and reconstructs the complete disclosure path.",
      before: "Output checks ask: did the answer contain a secret?",
      after: "Trace analysis asks: where did each sensitive value travel?",
      principles: ["Sources establish what the agent was allowed to see", "Disclosure channels establish what the agent emitted", "Distinct values are followed across events, not counted as isolated strings"],
    },
    steps: [
      { title: "Capture the trace", body: "Record events at trust boundaries: user input, tool calls and responses, memory, logs and the final output. Any framework works." },
      { title: "Normalize to 8 channels", body: "LangChain, LangGraph, CrewAI, MCP, OpenTelemetry and generic OpenAI-style logs all map to the same AgentLeak schema before analysis." },
      { title: "Replay and match", body: "Each channel is scanned with regex, Presidio, entropy and de-obfuscation detectors, matched against the vault, and reconstructed into a leak path." },
      { title: "Read the report", body: "Every finding lists the exact channel, a severity from L1 to L4, and a fix, in the CLI, the dashboard or a JSON report." },
    ],
    snippetLabel: "Analyze a trace from the CLI",
    snippet: "agentleak run --trace run.json --output ./reports --format html\nopen ./reports/run_0001.html",
  },
  agentrisk: {
    eyebrow: "AgentRisk scoring",
    title: "A privacy score your whole team can explain.",
    lede: "AgentRisk is a deterministic, severity-weighted risk index from 0 to 1, defined in a published benchmark. The same trace always yields the same score, so a regression in CI means the agent changed, not the judge.",
    metaTitle: "AgentRisk scoring · AgentLeak",
    metaDescription: "AgentRisk is a deterministic, severity-weighted privacy risk index from 0 to 1 with a readable 0-100 privacy score. Reproducible by design, so CI regressions are real.",
    demo: <RiskModelDemo />,
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
    concept: {
      title: "Risk is exposure relative to what the agent could reach.",
      body: "Counting findings alone makes a run with one leaked identifier look equivalent to a run leaking a medical record. AgentRisk weights distinct leaked values by sensitivity, then normalizes them against the audited vault. The result stays bounded, comparable and explainable.",
      before: "Finding counts reward noisy scanners and ignore sensitivity.",
      after: "AgentRisk measures weighted disclosure density from 0 to 1.",
      principles: ["L1-L4 weights reflect the sensitivity of each data type", "Repeated occurrences of one secret do not inflate global risk", "The closed-form score has no model variance or hidden prompt"],
    },
    steps: [
      { title: "Findings are collected", body: "Every match across the 8 normalized channels comes with a severity from L1 to L4, weighted by how sensitive the value is and how exposed the channel is." },
      { title: "Severity is weighted", body: "Higher severity findings and easier-to-exploit channels count for more in the closed-form scoring function, not an LLM's opinion." },
      { title: "The vault normalizes it", body: "The score is scaled 0 to 1 against the sensitive values actually present in the run, so a small trace and a huge one stay comparable." },
      { title: "The same trace, the same score", body: "No model decides the number, so a regression in CI means the agent changed behavior, never that the judge got moody." },
    ],
    snippetLabel: "Score a trace from the CLI",
    snippet: "agentleak run --trace run.json --format json --output ./reports\n# Risk Index 0.18 · privacy score 82 / 100\n# JSON report: ./reports/run_0001.json",
  },
  "code-scan": {
    eyebrow: "Pre-runtime scanning",
    title: "Catch hardcoded secrets before the agent ever runs.",
    lede: "Static code scan reads an agent's own source \u2014 a local directory, an uploaded zip, or a GitHub repo \u2014 for hardcoded secrets, PII in log statements and sensitive values sent to third parties, before a single trace is captured.",
    metaTitle: "Static code scan · AgentLeak",
    metaDescription: "AgentLeak's static code scan catches hardcoded secrets, logged PII and third-party data sends in an agent's own source before runtime, via `agentleak scan` or POST /api/agent/code.",
    demo: <AgentLoopDemo />,
    sections: [
      {
        title: "Three ways to submit code",
        body: "Point the scanner at a local directory, a zip file, or a GitHub repo and branch \u2014 it reads the same source your agent runs, not a sandboxed copy.",
        points: ["`agentleak scan <path>` for a local directory or .zip", "`agentleak scan --repo owner/name --branch main`", "POST /api/agent/code for an agent scanning itself", "Detector settings honour your project's agentleak.yaml"],
      },
      {
        title: "The same severity model",
        body: "Findings use the identical L1 to L4 severity scale as trace analysis, plus code-specific layers, so a hardcoded API key and a leaked account_id are directly comparable.",
        points: ["L1 to L4 severity per finding", "Entropy analysis for high-signal secrets", "De-obfuscation of decomposed PII", "File and line number per finding"],
      },
      {
        title: "Built for the agent loop",
        body: "POST /api/agent/code is part of the same scoped-key API an agent uses to self-test and improve, so a code scan can run automatically before every deploy.",
        points: ["POST /api/agent/code", "Scoped project API key (X-AgentLeak-Key)", "Re-scans the source declared in the agent card", "Pairs with the CI `--fail-under` gate"],
      },
    ],
    concept: {
      title: "A secret hardcoded once is a leak in every future run.",
      body: "Trace analysis catches what an agent does at runtime; static code scan catches what is already sitting in its source, waiting to be read, logged or sent to a third party. Running both closes the gap between what the agent was written to do and what it actually did in production.",
      before: "A hardcoded key or a debug print of raw PII waits, undetected, for the first run that exercises that code path.",
      after: "The scan flags the exact file and line before the agent is ever deployed.",
      principles: ["The same 3-tier pipeline as trace analysis: regex, Presidio, LLM-judge", "Redacted snippets are shown, never the raw secret itself", "One scan id per submission, comparable across commits"],
    },
    steps: [
      { title: "Point at the source", body: "Run the CLI against a local path, a .zip, or pass --repo owner/name to fetch a GitHub repository directly." },
      { title: "Scan runs the hybrid pipeline", body: "Regex, entropy and (optionally) Presidio and an LLM-judge scan every file, plus code-specific de-obfuscation and quasi-identifier correlation." },
      { title: "Read the findings", body: "Each finding lists the file, line, rule, data type and a redacted snippet, with an overall 0-100 code privacy score." },
      { title: "Gate on the score", body: "Pass --fail-under to exit non-zero when the code score drops below your threshold, exactly like the trace-analysis CI gate." },
    ],
    snippetLabel: "Scan a GitHub repo for hardcoded secrets",
    snippet: "agentleak scan --repo acme/support-bot --branch main --fail-under 80\n# Code privacy score: 74/100 \u2014 Conditional pass\n#   [L3] app/memory_adapter.py:42 hardcoded_api_key (secret, high-entropy)",
  },
  "red-team": {
    eyebrow: "Adversarial red-team",
    title: "Replay real attacks against your agent, not just clean traces.",
    lede: "32 scripted attack classes across 6 families \u2014 prompt & instruction, indirect & tool-surface, memory & persistence, multi-agent coordination, reasoning manipulation and evasion \u2014 run against your own agent, scripted or live.",
    metaTitle: "Adversarial red-team · AgentLeak",
    metaDescription: "AgentLeak replays 32 scripted attack classes across 6 families (prompt injection, tool-surface poisoning, memory persistence, multi-agent, reasoning and evasion) against your agent and scores the result with AgentRisk.",
    demo: <PipelineGateDemo />,
    sections: [
      {
        title: "Six attack families, three adversary levels",
        body: "Every attack class is tagged with the internal channel it targets and an adversary level from A0 (passive) to A2 (an attacker who controls tool outputs or shared memory).",
        points: ["F1 prompt & instruction", "F2 indirect & tool-surface", "F3 memory & persistence", "F4 multi-agent coordination", "F5 reasoning manipulation", "F6 evasion & obfuscation"],
      },
      {
        title: "Scripted or live",
        body: "Run attacks against a deterministic offline agent for repeatable regression tests, or against a real LLM endpoint to see how your actual agent responds under pressure.",
        points: ["Scripted mode: deterministic, no LLM cost", "Live mode: your own model via BYOK", "Pick a vertical, a count, or one specific class", "Same detection pipeline as any other trace"],
      },
      {
        title: "Same score, adversarial input",
        body: "Every red-team run is analyzed by the same AgentRisk pipeline as a normal trace, so an attack result is directly comparable to your project's baseline.",
        points: ["Risk Index and privacy score per scenario", "Attack class and family recorded per run", "Delta versus the project's prior best score", "Feeds the same leaderboard and history"],
      },
    ],
    concept: {
      title: "A clean benign trace does not tell you what an attacker would find.",
      body: "Passive testing only shows what your agent does when nothing is trying to break it. Red-team replay scripts the same 32-class taxonomy the published benchmark uses, so you see whether prompt injection, tool-response poisoning or a memory hand-off can pull sensitive data out of your agent before someone else tries it first.",
      before: "The only adversary your agent has faced is your own test suite.",
      after: "32 scripted attack classes across 3 adversary levels probe it first.",
      principles: ["Attack classes are grounded in a published 6-family / 32-class taxonomy", "Findings reuse the same channels, severity and AgentRisk score as any run", "Live mode never runs without an explicit agent endpoint you configure"],
    },
    steps: [
      { title: "Choose a target", body: "Pick a vertical (healthcare, finance, HR, customer support), an adversary level (A0-A2), and optionally one specific attack class." },
      { title: "Pick scripted or live", body: "Scripted replays a deterministic agent for regression testing; live sends the attack to your own configured model endpoint." },
      { title: "The batch runs", body: "Each generated scenario is executed and analyzed by the standard AgentLeak pipeline, exactly like a captured production trace." },
      { title: "Compare the results", body: "Every run records its attack class, family and channel alongside the Risk Index, so you can see which attack surface is weakest." },
    ],
    snippetLabel: "Request body for a red-team batch",
    snippet: "POST /api/projects/{project_id}/redteam\n{\n  \"vertical\": \"healthcare\",\n  \"n\": 5,\n  \"adversary_level\": \"A1\",\n  \"mode\": \"scripted\"\n}",
  },
  "ci-gate": {
    eyebrow: "CI policy gate",
    title: "Make privacy a required check, not an afterthought.",
    lede: "Set a policy per project and wire AgentLeak into CI. When an agent crosses its boundary, the check fails and the pull request is blocked, with the offending channel and severity attached to the run.",
    metaTitle: "CI policy gate · AgentLeak",
    metaDescription: "Wire AgentLeak into GitHub Actions, GitLab CI or any runner with a non-zero exit code. A privacy boundary crossing fails the job, and marking that job required blocks the merge with the trace, channel and severity attached as evidence.",
    demo: <PipelineGateDemo />,
    sections: [
      {
        title: "One boundary per project",
        body: "Define what counts as a failure (a channel, a severity level, a score threshold) and the gate enforces it on every run.",
        points: ["Fail below a privacy score", "Block a channel above a level", "Per-project, version-controlled policy", "Sensible defaults out of the box"],
      },
      {
        title: "Any CI runner, no plugin",
        body: "AgentLeak exits non-zero when a run crosses policy. GitHub Actions, GitLab CI and every other runner already treat a failing job as blockable \u2014 mark it required in branch protection and the merge stops itself, with no proprietary GitHub or GitLab app to install.",
        points: ["Non-zero exit code from the CLI", "Works in GitHub Actions, GitLab CI or any runner", "Mark the job required in branch protection", "No custom status-check integration to build"],
      },
      {
        title: "Evidence on the PR",
        body: "A blocked merge comes with the trace, the offending channel and the severity, so the author knows exactly what to fix.",
        points: ["Offending channel highlighted", "Severity and risk index shown", "Link straight to the full report", "The exact remediation attached"],
      },
    ],
    concept: {
      title: "A privacy policy becomes useful when it can stop a release.",
      body: "Dashboards are evidence after the fact. A gate turns the same evidence into an enforceable engineering boundary: which channels may disclose which levels, and what minimum privacy score a project must maintain. The policy lives beside the code and produces a normal CI status.",
      before: "Reviewers inspect a report after an agent has changed.",
      after: "The pull request cannot merge until the same trace passes policy.",
      principles: ["Policies are version-controlled per project", "Exit codes work in any CI runner without a proprietary action", "Every failure carries the channel, level and remediation needed to fix it"],
    },
    steps: [
      { title: "Set the policy", body: "Choose a score threshold, or forbid a specific channel/severity combination, per project and check it into version control." },
      { title: "Wire in the CLI", body: "One command in any shell, any runner: GitHub Actions, GitLab CI, a Makefile or a pre-merge hook." },
      { title: "Fail on crossing", body: "A boundary crossing exits non-zero, which fails the job exactly like any other failing test in the suite." },
      { title: "Attach the evidence", body: "The trace, the offending channel and the severity are written to the report and CLI output, so whoever marked the job required has exactly what they need to fix it before merging." },
    ],
    snippetLabel: "Gate a merge in CI",
    snippet: "# .github/workflows/agentleak.yml\n- name: Privacy gate\n  run: agentleak run --trace traces/latest.json --config agentleak.yaml --fail-under 80",
  },
  "agent-api": {
    eyebrow: "Built for autonomous agents",
    title: "Agents can discover, test and fix themselves.",
    lede: "llms.txt discovery, one-call onboarding, scoped project keys and machine-readable remediation hints. An agent can find AgentLeak, audit itself and fix its own leaks in a bounded loop, with no browser and no human in the middle.",
    metaTitle: "Agent API · AgentLeak",
    metaDescription: "AgentLeak exposes a machine-first API: llms.txt discovery, one-call onboarding, scoped keys and structured remediation hints so autonomous agents can self-test and improve in a loop.",
    demo: <AgentLoopDemo />,
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
    concept: {
      title: "Privacy testing can be part of an agent's own control loop.",
      body: "AgentLeak exposes discovery, onboarding, testing and remediation as machine-readable contracts. A capable agent does not need to interpret a dashboard: it submits a trace, receives bounded actions, applies one change and verifies the same scenario again.",
      before: "A human notices a leak, translates the report and asks for a fix.",
      after: "The agent consumes structured evidence and proves the fix itself.",
      principles: ["Scoped credentials limit what an autonomous client can access", "Remediation hints name one channel and one concrete action", "Each iteration reports a score delta so improvement is measurable"],
    },
    steps: [
      { title: "Discover", body: "An agent reads /llms.txt or /.well-known/agent-card.json to learn the API surface with no human in the loop." },
      { title: "Onboard", body: "One call to /api/agent/onboard creates a scoped project key with a free monthly quota, ready to use immediately." },
      { title: "Self-test", body: "POST /api/selftest with its own trace and get back findings, a compliance verdict and structured remediation hints." },
      { title: "Improve and loop", body: "POST /api/agent/improve to get a delta versus the previous run and priority-sorted next steps, then repeat until clean." },
    ],
    snippetLabel: "Onboard an agent in one call",
    snippet: "curl -sX POST https://agents.fomox.com/api/agent/onboard \\\n  -H 'content-type: application/json' \\\n  -d '{\"email\":\"agent@example.com\",\"agent_name\":\"SupportBot\"}'",
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
              <Link className="cursor-button cursor-button-dark" to="/register">Create a workspace <Arrow /></Link>
              <Link className="cursor-button cursor-button-light" to="/docs/agents">Agents: discover and onboard <Arrow /></Link>
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

        <section className="cursor-concept">
          <div className="cursor-concept-copy">
            <p className="cursor-eyebrow">The mental model</p>
            <h2>{content.concept.title}</h2>
            <p>{content.concept.body}</p>
          </div>
          <div className="cursor-concept-shift">
            <div><small>Before</small><p>{content.concept.before}</p></div>
            <span aria-hidden="true">→</span>
            <div data-after="true"><small>With AgentLeak</small><p>{content.concept.after}</p></div>
          </div>
          <ul>{content.concept.principles.map((principle) => <li key={principle}>{principle}</li>)}</ul>
        </section>

        <section className="docs-section cursor-page-howto">
          <header><p className="cursor-eyebrow">How it works</p><h2>From raw trace to a fix, in four steps.</h2></header>
          <div className="docs-steps">
            {content.steps.map((step, index) => (
              <div key={step.title}>
                <b>{index + 1}</b>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </div>
            ))}
          </div>
          <div className="cursor-page-snippet">
            <p className="cursor-eyebrow">{content.snippetLabel}</p>
            <Code>{content.snippet}</Code>
          </div>
        </section>

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
