import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import {
  Activity,
  FlaskConical,
  FolderKanban,
  Gauge,
  LayoutDashboard,
  Library,
  Settings,
  ShieldAlert,
  Trophy,
} from "lucide-react"
import type { RunSummary } from "@/lib/api"
import { BrandLogo, ECOSYSTEM_LOGOS } from "@/features/BrandLogos"

const PAPER_URL = "https://arxiv.org/abs/2602.11510"
const REPO_URL = "https://github.com/yagobski/agentleak-oss"

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false)
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)")
    const update = () => setReduced(media.matches)
    update()
    media.addEventListener("change", update)
    return () => media.removeEventListener("change", update)
  }, [])
  return reduced
}

function Brand() {
  return (
    <Link to="/" className="cursor-brand" aria-label="AgentLeak home">
      <span className="cursor-brand-mark" aria-hidden="true"><i /><i /><i /></span>
      <span>AGENTLEAK</span>
    </Link>
  )
}

function Arrow() {
  return <span aria-hidden="true">→</span>
}

// Faithful miniature of the real Dashboard (layout/AppShell + pages/Dashboard):
// same sidebar, same stat cards, same run rows, filled with complete demo data
// so the hero shows what a working workspace actually looks like.
const HERO_RUNS = [
  ["support-router", "agent:selftest", "now", "0.38", "Fail", "2 leaked", true],
  ["claims-reviewer", "ci · release-42", "8m", "0.12", "Pass", "clean", false],
  ["patient-summary", "ci · nightly", "21m", "0.64", "Blocked", "4 leaked", true],
  ["finance-copilot", "playground", "1h", "0.08", "Pass", "clean", false],
  ["onboarding-bot", "agent:improve", "2h", "0.22", "Conditional", "1 leaked", true],
] as const

function HeroPlatform() {
  const [activeRun, setActiveRun] = useState(0)
  const reducedMotion = usePrefersReducedMotion()

  useEffect(() => {
    if (reducedMotion) return
    const timer = window.setInterval(() => setActiveRun((current) => (current + 1) % HERO_RUNS.length), 2100)
    return () => window.clearInterval(timer)
  }, [reducedMotion])

  return (
    <div className="cursor-demo cursor-app" aria-label="The AgentLeak dashboard with a full workspace of scored agents">
      <div className="cursor-demo-bar">
        <div><span /><span /><span /></div>
        <p>AgentLeak / Dashboard</p>
        <b>100% local · v0.8.0</b>
      </div>
      <div className="cursor-app-body">
        <aside className="cursor-app-side">
          <b className="cursor-app-brand">AGENTLEAK<small>Agent privacy testing</small></b>
          <small>Platform</small>
          <span data-active="true"><LayoutDashboard /> Dashboard</span>
          <span><FolderKanban /> Projects</span>
          <span><FlaskConical /> Playground</span>
          <span><Library /> Scenarios</span>
          <div className="cursor-app-side-foot">
            <span><Settings /> Settings</span>
            <em>acme-ops</em>
          </div>
        </aside>
        <section className="cursor-app-main">
          <header className="cursor-app-head">
            <div><h4>Dashboard</h4><p>Privacy posture across your agents, scored with AgentRisk.</p></div>
            <b>Projects</b>
          </header>
          <div className="cursor-app-stats">
            <div><small>Projects <FolderKanban /></small><strong>6</strong><span>Agents under test</span></div>
            <div><small>Runs <Activity /></small><strong>128</strong><span>Analyses stored</span></div>
            <div><small>Avg risk index <Gauge /></small><strong>0.24</strong><span>Conditional pass</span></div>
            <div><small>Blocked runs <ShieldAlert /></small><strong>3</strong><span>Would fail a CI gate</span></div>
          </div>
          <div className="cursor-app-columns">
            <div className="cursor-app-runs">
              <header><span>Recent runs</span><code>last 24h</code></header>
              {HERO_RUNS.map(([agent, source, when, ri, verdict, leaks, hot], index) => (
                <article key={agent} data-active={index === activeRun} data-hot={hot}>
                  <b>{agent}</b>
                  <small>{source}</small>
                  <span>{leaks} · RI {ri}</span>
                  <em data-verdict={verdict}>{verdict}</em>
                  <code>{when}</code>
                </article>
              ))}
            </div>
            <div className="cursor-app-rail">
              <div className="cursor-app-card">
                <span><FlaskConical /> Quick audit</span>
                <p>Score a trace instantly without creating a project.</p>
                <b>Open playground <Arrow /></b>
              </div>
              <div className="cursor-app-card">
                <span><Trophy /> Agent leaderboard</span>
                {[["finance-copilot", "92"], ["claims-reviewer", "88"], ["support-router", "62"]].map(([name, score], index) => (
                  <div className="cursor-app-rank" key={name}><i>{index + 1}</i><b>{name}</b><code>{score}</code></div>
                ))}
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

// Faithful miniature of a real run report (pages/RunView): per-channel risk,
// concrete findings with severity levels, and the remediation hint an agent
// can act on, the artifact you actually get from an analysis.
const REPORT_CHANNELS = [
  ["user_input", "Customer message received", "clean", ""],
  ["tool_call", "email + account_id sent to calendar.create", "L3", "EMAIL · ACCOUNT_ID"],
  ["shared_memory", "account_id persisted for the next agent", "L2", "ACCOUNT_ID"],
  ["log", "No sensitive values written", "clean", ""],
  ["final_output", "Clean answer to the customer", "clean", ""],
] as const

function RunReportDemo() {
  const [activeRow, setActiveRow] = useState(1)
  const reducedMotion = usePrefersReducedMotion()

  useEffect(() => {
    if (reducedMotion) return
    const timer = window.setInterval(() => setActiveRow((current) => (current + 1) % REPORT_CHANNELS.length), 2000)
    return () => window.clearInterval(timer)
  }, [reducedMotion])

  return (
    <div className="cursor-report" aria-label="A real AgentLeak run report: channel risks, findings and the remediation hint">
      <div className="cursor-report-head">
        <div><b>support-router</b><small>run_2048 · selftest · 4 events</small></div>
        <span data-verdict="Fail">Fail · RI 0.38</span>
      </div>
      <div className="cursor-report-score">
        <strong>62</strong>
        <div><span>/ 100 privacy score</span><i><b style={{ width: "38%" }} /></i></div>
        <dl>
          <div><dt>Distinct leaks</dt><dd>2</dd></div>
          <div><dt>Channels</dt><dd>2 / 6</dd></div>
        </dl>
      </div>
      {REPORT_CHANNELS.map(([channel, description, level, types], index) => (
        <div className="cursor-report-row" data-active={index === activeRow} data-leak={level !== "clean"} key={channel}>
          <code>{channel}</code>
          <div><strong>{description}</strong>{types && <small>{types}</small>}</div>
          <b>{level === "clean" ? "clean" : level}</b>
        </div>
      ))}
      <div className="cursor-report-fix">
        <span>Remediation 01</span>
        <p>Redact <code>account_id</code> before <code>calendar.create</code>. Ready-to-paste fix included.</p>
      </div>
    </div>
  )
}

const now = Math.floor(Date.now() / 1000)
const demoRuns: RunSummary[] = [
  { id: "demo-1", project_id: "demo", created_at: now - 80, source: "agent:selftest", agent_name: "support-router", risk_index: .38, privacy_score: 62, verdict: "High risk", blocked: false, leaked_secrets: 2, label: "handoff" },
  { id: "demo-2", project_id: "demo", created_at: now - 900, source: "agent:selftest", agent_name: "claims-reviewer", risk_index: .17, privacy_score: 83, verdict: "Conditional pass", blocked: false, leaked_secrets: 1, label: "memory" },
  { id: "demo-3", project_id: "demo", created_at: now - 3900, source: "ci", agent_name: "patient-summary", risk_index: .64, privacy_score: 36, verdict: "Fail", blocked: true, leaked_secrets: 4, label: "release-42" },
]

function PlatformWorkbench() {
  return (
    <div className="cursor-workbench" aria-label="AgentRisk trend, policy gate and recent runs">
      <aside>
        <b>AGENTLEAK</b>
        <span data-active="true">Dashboard</span>
        <span>Projects</span>
        <span>Scenarios</span>
        <span>Policies</span>
      </aside>
      <section>
        <header>
          <span>AgentRisk trend</span>
          <em>4 recent runs</em>
        </header>
        <div className="cursor-workbench-stats">
          <div><small>Avg RI</small><strong>0.31</strong><span>lower is safer</span></div>
          <div><small>Privacy</small><strong>68</strong><span>/100 average</span></div>
          <div><small>Gate</small><strong>1</strong><span>blocked release</span></div>
        </div>
        <div className="cursor-workbench-main">
          <div className="cursor-workbench-chart">
            <span>Risk Index</span>
            <svg viewBox="0 0 440 142" role="img" aria-label="Risk Index trend across recent runs">
              {[20, 70, 120].map((y) => <line key={y} x1="18" x2="422" y1={y} y2={y} />)}
              <path d="M22 105 L148 61 L272 93 L418 76" />
              <circle cx="22" cy="105" r="4" />
              <circle cx="148" cy="61" r="4" data-hot="true" />
              <circle cx="272" cy="93" r="4" />
              <circle cx="418" cy="76" r="4" />
            </svg>
          </div>
          <div className="cursor-workbench-policy">
            <span>Policy gate</span>
            <p>Block tool_call and shared_memory exposures above L3.</p>
            <b>Active in CI</b>
          </div>
        </div>
        <div className="cursor-workbench-runs">
          {demoRuns.map((run) => (
            <article key={run.id} data-blocked={run.blocked}>
              <span>{run.verdict}</span>
              <b>{run.agent_name}</b>
              <small>{run.leaked_secrets} leaked · RI {run.risk_index.toFixed(2)}</small>
              <em>{run.blocked ? "Blocked" : run.label}</em>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}

// A GitHub-style checks panel: privacy as a required status check that blocks
// the merge, the way a team actually adopts AgentLeak in CI.
function CIGateDemo() {
  return (
    <div className="cursor-ci" aria-label="AgentLeak as a required CI status check that blocks a merge">
      <div className="cursor-ci-head"><b>feat: multi-agent claims workflow</b><small>#428 opened by claims-reviewer</small></div>
      <div className="cursor-ci-body">
        <div className="cursor-ci-check" data-state="ok"><i /><span>build</span><em>passed</em></div>
        <div className="cursor-ci-check" data-state="ok"><i /><span>unit tests</span><em>passed</em></div>
        <div className="cursor-ci-check" data-state="fail">
          <i /><span>AgentLeak / privacy-gate</span><em>failed</em>
        </div>
        <div className="cursor-ci-detail">
          <p><b>shared_memory</b> leaked <code>account_id</code> at level <b>L3</b>, above the project policy (L2).</p>
          <p>Risk Index 0.38 · privacy score 62 / 100</p>
        </div>
        <div className="cursor-ci-check" data-state="ok"><i /><span>e2e</span><em>passed</em></div>
      </div>
      <div className="cursor-ci-foot"><b data-blocked="true">Merge blocked</b><span>1 required check failed</span></div>
    </div>
  )
}

// A terminal that reads like the real install path: pip / docker, MIT, local.
function OpenSourceDemo() {
  return (
    <div className="cursor-oss" aria-label="Install and run AgentLeak locally, open source under MIT">
      <div className="cursor-oss-bar"><div><span /><span /><span /></div><b>MIT · self-host</b></div>
      <code className="cursor-oss-code">
        <span><i>$</i> pip install agentleak</span>
        <span><i>$</i> agentleak run --trace run.json</span>
        <span><em>AgentRisk 0.38 · 2 exposures · policy failed</em></span>
        <span><i>$</i> docker compose up -d <b># hosted, free for agents</b></span>
      </code>
      <div className="cursor-oss-foot">
        <div><strong>MIT</strong><small>license</small></div>
        <div><strong>100%</strong><small>local, no telemetry</small></div>
        <div><strong>0</strong><small>hosted model required</small></div>
      </div>
    </div>
  )
}

// A minimal research card standing in for the published benchmark.
function ResearchCard() {
  return (
    <div className="cursor-paper" aria-label="The AgentLeak research benchmark this tool implements">
      <div className="cursor-paper-head"><span>arXiv:2602.11510</span><em>Benchmark</em></div>
      <h4>AgentLeak: measuring privacy leakage across agent execution traces</h4>
      <div className="cursor-paper-stats">
        <div><strong>36</strong><small>scenarios</small></div>
        <div><strong>4</strong><small>domains</small></div>
        <div><strong>A0-A2</strong><small>adversary levels</small></div>
      </div>
      <p>Healthcare · Finance · Legal · Corporate. AgentRisk is the severity-weighted score defined in the paper; this tool is its open implementation.</p>
    </div>
  )
}

export function Landing() {
  return (
    <div className="cursor-site">
      <header className="cursor-nav">
        <Brand />
        <nav aria-label="Main navigation">
          <a href="#product">Product</a>
          <a href="#workflow">How it works</a>
          <a href="#research">Research</a>
          <Link to="/docs">Documentation</Link>
        </nav>
        <div className="cursor-nav-actions">
          <a className="cursor-nav-gh" href={REPO_URL} aria-label="AgentLeak on GitHub">GitHub</a>
          <Link to="/login">Sign in</Link>
          <Link className="cursor-pill cursor-pill-dark" to="/register">Start testing</Link>
        </div>
      </header>

      <main>
        <section className="cursor-hero" id="product">
          <div className="cursor-hero-copy">
            <a className="cursor-hero-tag" href={REPO_URL}>Open source · MIT · runs 100% local <Arrow /></a>
            <h1>AgentLeak tests what your agents expose before the final answer.</h1>
            <p>
              An agent can return one clean answer while copying customer data into a tool call,
              shared memory, a log or a generated file along the way. AgentLeak replays the whole
              execution trace, scores every internal channel with AgentRisk, and returns the exact
              fix to you or to your agent.
            </p>
            <div className="cursor-actions">
              <Link className="cursor-button cursor-button-dark" to="/register">Run your first audit <Arrow /></Link>
              <Link className="cursor-button cursor-button-light" to="/docs">Read the documentation <Arrow /></Link>
            </div>
          </div>
          <HeroPlatform />
        </section>

        <section className="cursor-trust">
          <h2>Built on the agent frameworks and runtimes you already use</h2>
          <div className="cursor-logo-grid">
            {ECOSYSTEM_LOGOS.map((logo) => (
              <span key={logo.name}><BrandLogo logo={logo} /><b>{logo.name}</b></span>
            ))}
          </div>
          <p>Compatibility, not customer endorsement. Framework adapters, OpenTelemetry ingestion and generic traces all normalize to one AgentLeak schema.</p>
        </section>

        <section className="cursor-capabilities">
          <header>
            <p className="cursor-eyebrow">What the platform does</p>
            <h2>One workspace for the whole privacy loop.</h2>
          </header>
          <div>
            {[
              ["Trace analysis", "Replay any run across six channels (tools, memory, messages, logs, files, output) and find every exposure."],
              ["AgentRisk scoring", "A deterministic, severity-weighted risk index from 0 to 1 and a 0 to 100 privacy score. No model decides the number."],
              ["Static code scan", "Catch hardcoded secrets, PII in logs and sensitive values sent to third parties before the agent even runs."],
              ["Adversarial red-team", "Replay prompt-injection and exfiltration attack classes against your agent, scripted or live."],
              ["CI policy gate", "Set a boundary per project. A crossing blocks the build, with the trace attached as evidence."],
              ["Agent self-serve API", "Agents onboard in one call, test themselves and follow a bounded remediation loop, with no human in the middle."],
            ].map(([title, description], index) => (
              <article key={title}><span>{String(index + 1).padStart(2, "0")}</span><h3>{title}</h3><p>{description}</p></article>
            ))}
          </div>
        </section>

        <section className="cursor-feature cursor-feature-lead" id="workflow">
          <div className="cursor-feature-copy">
            <p className="cursor-eyebrow">Complete trace analysis</p>
            <h2>The final output can be clean while the system is leaking.</h2>
            <p>Output-only checks miss what happens inside the run. AgentLeak follows sensitive values through every internal channel, reconstructs where exposure happened, assigns each finding a severity level from L1 to L4, and returns the exact remediation: prose for your team, and structured hints an agent can apply.</p>
            <Link className="cursor-textlink" to="/docs">Understand the trace model <Arrow /></Link>
          </div>
          <RunReportDemo />
        </section>

        <section className="cursor-feature cursor-feature-reverse">
          <div className="cursor-feature-copy">
            <p className="cursor-eyebrow">AgentRisk</p>
            <h2>A score your team can explain.</h2>
            <p>Severity-weighted risk from 0 to 1, normalized against the audited sensitive vault. Deterministic and reproducible: the same trace always yields the same score, so a regression in CI means the agent changed, not the judge.</p>
            <Link className="cursor-textlink" to="/docs#agentrisk">Learn how scoring works <Arrow /></Link>
          </div>
          <PlatformWorkbench />
        </section>

        <section className="cursor-feature">
          <div className="cursor-feature-copy">
            <p className="cursor-eyebrow">Ship with confidence</p>
            <h2>Make privacy a required check, not a code review afterthought.</h2>
            <p>Set a policy per project and wire AgentLeak into CI. When an agent crosses its boundary, the check fails and the pull request is blocked, with the offending channel and severity attached to the run.</p>
            <Link className="cursor-textlink" to="/docs">See CI integration <Arrow /></Link>
          </div>
          <CIGateDemo />
        </section>

        <section className="cursor-feature cursor-feature-reverse">
          <div className="cursor-feature-copy">
            <p className="cursor-eyebrow">Built for autonomous agents</p>
            <h2>Agents can discover, test and improve themselves.</h2>
            <p>llms.txt discovery, one-call onboarding, scoped project keys and machine-readable remediation hints. An agent can find AgentLeak, audit itself and fix its own leaks in a bounded loop, with no browser and no human in the middle.</p>
            <Link className="cursor-textlink" to="/docs/agents">Read agent instructions <Arrow /></Link>
          </div>
          <div className="cursor-terminal"><div><span /><span /><span /></div><code><span><i>$</i> curl agents.fomox.com/llms.txt</span><span><i>$</i> POST /api/agent/onboard</span><span><b>project created</b></span><span><i>$</i> POST /api/selftest</span><span><em>2 exposures · policy failed</em></span></code></div>
        </section>

        <section className="cursor-feature">
          <div className="cursor-feature-copy">
            <p className="cursor-eyebrow">Open source</p>
            <h2>Local-first, MIT, no telemetry.</h2>
            <p>The analyzer runs entirely on your machine. Free detection (regex, Presidio, entropy, de-obfuscation) needs no hosted model and no external detector. Run it as a CLI, self-host the platform, or use the free hosted instance for agents.</p>
            <a className="cursor-textlink" href={REPO_URL}>Star it on GitHub <Arrow /></a>
          </div>
          <OpenSourceDemo />
        </section>

        <section className="cursor-scenarios" id="scenarios">
          <header><h2>Start with scenarios that match real agent boundaries.</h2><p>Use synthetic traces to establish a baseline, then connect an authorized staging workflow.</p></header>
          <div>
            {[
              ["01", "Support operations", "CRM lookup, internal handoff, ticket update", "Email, address, account ID"],
              ["02", "Healthcare", "Patient record, summary agent, generated report", "Diagnosis, health ID, date of birth"],
              ["03", "Finance", "Account data, risk agent, external tool", "Card, income, transaction"],
              ["04", "Multi-agent systems", "Planner, specialist, reviewer, shared memory", "Credentials, internal IDs, PII"],
            ].map(([number, title, path, data]) => (
              <article key={number}><span>{number}</span><h3>{title}</h3><p>{path}</p><small>{data}</small></article>
            ))}
          </div>
          <Link className="cursor-textlink" to="/register">Run a bundled scenario <Arrow /></Link>
        </section>

        <section className="cursor-research" id="research">
          <div className="cursor-research-copy">
            <p className="cursor-eyebrow">Grounded in published research</p>
            <h2>AgentLeak and AgentRisk are not marketing terms.</h2>
            <p>The framework and its scoring method come from a published benchmark of privacy leakage across agent execution traces. This tool is the open implementation of that work: the same channels, the same severity model, the same AgentRisk score.</p>
            <div className="cursor-research-links">
              <a className="cursor-textlink" href={PAPER_URL}>Read the AgentLeak paper <Arrow /></a>
              <Link className="cursor-textlink" to="/docs#agentrisk">AgentRisk methodology <Arrow /></Link>
            </div>
          </div>
          <ResearchCard />
        </section>

        <section className="cursor-proof">
          <header><p className="cursor-eyebrow">Where AgentLeak sits</p><h2>A specific layer in the agent stack.</h2></header>
          <div>
            <article>
              <span><FlaskConical /></span>
              <h3>Local by default</h3>
              <p>The open-source analyzer works without telemetry, a hosted model or an external detector. Your traces never leave your machine.</p>
            </article>
            <article>
              <span><Activity /></span>
              <h3>Trace-wide evidence</h3>
              <p>Audit the internal disclosure channels that output-only guardrails and red-team prompts cannot observe.</p>
            </article>
            <article>
              <span><ShieldAlert /></span>
              <h3>Bounded claims</h3>
              <p>A passing test proves the tested trace met its configured policy. It is evidence, not a universal safety guarantee.</p>
            </article>
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

      <footer className="cursor-footer">
        <Brand />
        <div><h3>Product</h3><Link to="/register">Platform</Link><Link to="/docs#agentrisk">AgentRisk</Link><Link to="/docs/agents">For agents</Link></div>
        <div><h3>Resources</h3><Link to="/docs">Documentation</Link><Link to="/docs/developers">Developers</Link><a href={PAPER_URL}>Research paper</a></div>
        <div><h3>Open source</h3><a href={REPO_URL}>GitHub</a><a href="/openapi.json">OpenAPI</a><a href="/llms.txt">llms.txt</a></div>
        <p>© 2026 AgentLeak · MIT licensed · <a href={PAPER_URL}>arXiv:2602.11510</a></p>
      </footer>
    </div>
  )
}
