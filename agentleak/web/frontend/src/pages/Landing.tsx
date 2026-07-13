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
// same sidebar, same stat cards, same run rows — filled with complete demo data
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
        <p>AgentLeak — Dashboard</p>
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
// can act on — the artifact you actually get from an analysis.
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
        <p>Redact <code>account_id</code> before <code>calendar.create</code> — ready-to-paste fix included.</p>
      </div>
    </div>
  )
}

const integrations = ["LangChain", "LangGraph", "CrewAI", "AutoGen", "OpenAI Agents", "LlamaIndex", "OpenTelemetry", "MCP"]
const now = Math.floor(Date.now() / 1000)
const demoRuns: RunSummary[] = [
  { id: "demo-1", project_id: "demo", created_at: now - 80, source: "agent:selftest", agent_name: "support-router", risk_index: .38, privacy_score: 62, verdict: "High risk", blocked: false, leaked_secrets: 2, label: "handoff" },
  { id: "demo-2", project_id: "demo", created_at: now - 900, source: "agent:selftest", agent_name: "claims-reviewer", risk_index: .17, privacy_score: 83, verdict: "Conditional pass", blocked: false, leaked_secrets: 1, label: "memory" },
  { id: "demo-3", project_id: "demo", created_at: now - 3900, source: "ci", agent_name: "patient-summary", risk_index: .64, privacy_score: 36, verdict: "Fail", blocked: true, leaked_secrets: 4, label: "release-42" },
  { id: "demo-4", project_id: "demo", created_at: now - 8400, source: "ci", agent_name: "finance-copilot", risk_index: .08, privacy_score: 92, verdict: "Pass", blocked: false, leaked_secrets: 0, label: "baseline" },
]

function PlatformWorkbench() {
  return (
    <div className="cursor-workbench" aria-label="Synthetic AgentLeak platform preview">
      <aside>
        <b>AGENTLEAK</b>
        <span data-active="true">Dashboard</span>
        <span>Projects</span>
        <span>Scenarios</span>
        <span>Policies</span>
      </aside>
      <section>
        <header>
          <span>AgentLeak dashboard</span>
          <em>Synthetic demo data</em>
        </header>
        <div className="cursor-workbench-stats">
          <div><small>Avg RI</small><strong>0.31</strong><span>4 recent runs</span></div>
          <div><small>Privacy</small><strong>68</strong><span>/100 average</span></div>
          <div><small>Gate</small><strong>1</strong><span>blocked release</span></div>
        </div>
        <div className="cursor-workbench-main">
          <div className="cursor-workbench-chart">
            <span>Risk Index</span>
            <svg viewBox="0 0 440 142" role="img" aria-label="Risk Index trend">
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
          {demoRuns.slice(0, 3).map((run) => (
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

export function Landing() {
  return (
    <div className="cursor-site">
      <header className="cursor-nav">
        <Brand />
        <nav aria-label="Main navigation">
          <a href="#product">Product</a>
          <a href="#workflow">How it works</a>
          <a href="#scenarios">Scenarios</a>
          <Link to="/docs">Documentation</Link>
        </nav>
        <div className="cursor-nav-actions">
          <Link to="/login">Sign in</Link>
          <Link className="cursor-pill cursor-pill-outline" to="/docs/agents">For agents</Link>
          <Link className="cursor-pill cursor-pill-dark" to="/register">Start testing</Link>
        </div>
      </header>

      <main>
        <section className="cursor-hero" id="product">
          <div className="cursor-hero-copy">
            <h1>AgentLeak tests what your agents expose before the final answer.</h1>
            <p>
              An agent can return one clean answer while copying customer data into a tool call,
              shared memory, a log or a generated file along the way. AgentLeak replays the complete
              execution trace, scores every internal channel with AgentRisk, and hands you — or your
              agent — the exact fix.
            </p>
            <div className="cursor-actions">
              <Link className="cursor-button cursor-button-dark" to="/register">Run your first audit <Arrow /></Link>
              <Link className="cursor-button cursor-button-light" to="/docs">Read the documentation <Arrow /></Link>
            </div>
          </div>
          <HeroPlatform />
        </section>

        <section className="cursor-trust">
          <h2>Works with the agent frameworks and protocols you already use</h2>
          <div className="cursor-integration-grid">{integrations.map((integration, index) => <span key={integration}><i>{String(index + 1).padStart(2, "0")}</i><b>{integration}</b></span>)}</div>
          <p>Compatibility, not customer endorsement. Framework adapters and generic trace ingestion use the same AgentLeak schema.</p>
        </section>

        <section className="cursor-capabilities">
          <header>
            <p className="cursor-eyebrow">What the platform does</p>
            <h2>One workspace for the whole privacy loop.</h2>
          </header>
          <div>
            {[
              ["Trace analysis", "Replay any run across 6 channels — tools, memory, messages, logs, files, output — and find every exposure."],
              ["AgentRisk scoring", "A deterministic, severity-weighted 0–1 index and a 0–100 privacy score. No model decides the number."],
              ["Static code scan", "Catch hardcoded secrets, PII in logs and sensitive values sent to third parties before the agent even runs."],
              ["Adversarial red-team", "Replay prompt-injection and exfiltration attack classes against your agent, scripted or live."],
              ["CI policy gate", "Set a boundary per project; a crossing blocks the build with the trace as evidence."],
              ["Agent self-serve API", "Agents onboard with one call, test themselves and follow a bounded remediation loop — no human needed."],
            ].map(([title, description], index) => (
              <article key={title}><span>{String(index + 1).padStart(2, "0")}</span><h3>{title}</h3><p>{description}</p></article>
            ))}
          </div>
        </section>

        <section className="cursor-feature cursor-feature-lead" id="workflow">
          <div className="cursor-feature-copy">
            <p className="cursor-eyebrow">Complete trace analysis</p>
            <h2>The final output can be clean while the system is leaking.</h2>
            <p>Output-only checks miss what happens inside the run. AgentLeak follows sensitive values through every internal channel, reconstructs where exposure happened, assigns each finding a severity level (L1–L4) and returns the exact remediation — as prose for your team and as structured hints an agent can apply.</p>
            <Link to="/docs">Understand the trace model <Arrow /></Link>
          </div>
          <RunReportDemo />
        </section>

        <section className="cursor-feature-grid">
          <article>
            <div>
              <p className="cursor-eyebrow">AgentRisk</p>
              <h3>A score your team can explain.</h3>
              <p>Severity-weighted risk from 0 to 1, normalized against the audited sensitive vault. Deterministic and reproducible: the same trace always yields the same score, so a regression in CI means the agent changed — not the judge.</p>
              <Link to="/docs#agentrisk">Learn how scoring works <Arrow /></Link>
            </div>
            <PlatformWorkbench />
          </article>
          <article>
            <div>
              <p className="cursor-eyebrow">Built for autonomous agents</p>
              <h3>Agents can discover, test and improve themselves.</h3>
              <p>llms.txt discovery, one-call onboarding, scoped project keys and machine-readable remediation hints: an agent can find AgentLeak, audit itself and fix its own leaks in a bounded loop — no browser, no human in the middle.</p>
              <Link to="/docs/agents">Read agent instructions <Arrow /></Link>
            </div>
            <div className="cursor-terminal"><div><span /><span /><span /></div><code><span><i>$</i> curl agents.fomox.com/llms.txt</span><span><i>$</i> POST /api/agent/onboard</span><span><b>project created</b></span><span><i>$</i> POST /api/selftest</span><span><em>2 exposures · policy failed</em></span></code></div>
          </article>
        </section>

        <section className="cursor-scenarios" id="scenarios">
          <header><h2>Start with scenarios that match real agent boundaries.</h2><p>Use synthetic traces to establish a baseline, then connect an authorized staging workflow.</p></header>
          <div>
            {[
              ["01", "Support operations", "CRM lookup → internal handoff → ticket update", "Email, address, account ID"],
              ["02", "Healthcare", "Patient record → summary agent → generated report", "Diagnosis, health ID, date of birth"],
              ["03", "Finance", "Account data → risk agent → external tool", "Card, income, transaction"],
              ["04", "Multi-agent systems", "Planner → specialist → reviewer → shared memory", "Credentials, internal IDs, PII"],
            ].map(([number, title, path, data]) => (
              <article key={number}><span>{number}</span><h3>{title}</h3><p>{path}</p><small>{data}</small></article>
            ))}
          </div>
          <Link to="/register">Run a bundled scenario <Arrow /></Link>
        </section>

        <section className="cursor-proof">
          <h2>A specific layer in the agent stack.</h2>
          <div>
            <article><span>01</span><h3>Local by default</h3><p>The open-source analyzer works without telemetry, a hosted model or an external detector.</p></article>
            <article><span>02</span><h3>Trace-wide evidence</h3><p>Audit internal disclosure channels that output-only checks cannot observe.</p></article>
            <article><span>03</span><h3>Bounded claims</h3><p>A passing test proves the tested trace met its configured policy — not universal safety.</p></article>
          </div>
        </section>

        <section className="cursor-final-cta">
          <h2>Test the path, not only the answer.</h2>
          <Link className="cursor-button cursor-button-dark" to="/register">Start testing AgentLeak <Arrow /></Link>
        </section>
      </main>

      <footer className="cursor-footer">
        <Brand />
        <div><h3>Product</h3><Link to="/register">Platform</Link><Link to="/docs#agentrisk">AgentRisk</Link><Link to="/docs/agents">For agents</Link></div>
        <div><h3>Resources</h3><Link to="/docs">Documentation</Link><Link to="/docs/developers">Developers</Link><Link to="/docs/api">API reference</Link></div>
        <div><h3>Open source</h3><a href="https://github.com/yagobski/agentleak-oss">GitHub</a><a href="/openapi.json">OpenAPI</a><a href="/llms.txt">llms.txt</a></div>
        <p>© 2026 AgentLeak</p>
      </footer>
    </div>
  )
}
