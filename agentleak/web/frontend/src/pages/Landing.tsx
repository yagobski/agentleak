import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
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

function ProductDemo() {
  const [activeEvent, setActiveEvent] = useState(0)
  const reducedMotion = usePrefersReducedMotion()
  const events = [
    ["01", "tool_response", "CRM returned customer record", "source"],
    ["02", "tool_call", "Email forwarded to calendar", "leak"],
    ["03", "shared_memory", "Account ID copied to shared state", "leak"],
    ["04", "final_output", "Appointment confirmed", "clean"],
  ]

  useEffect(() => {
    if (reducedMotion) return
    const timer = window.setInterval(() => setActiveEvent((current) => (current + 1) % events.length), 1700)
    return () => window.clearInterval(timer)
  }, [events.length, reducedMotion])

  const privacyScores = [100, 81, 62, 62]
  const riskIndexes = ["0.00", "0.19", "0.38", "0.38"]
  const privacyScore = privacyScores[activeEvent]
  const riskIndex = riskIndexes[activeEvent]

  return (
    <div className="cursor-demo" aria-label="AgentLeak trace analysis product preview">
      <div className="cursor-demo-bar">
        <div><span /><span /><span /></div>
        <p>AgentLeak / support-agent / run_2048</p>
        <b>{activeEvent === events.length - 1 ? "Analysis complete" : `Tracing event ${activeEvent + 1} / ${events.length}`}</b>
      </div>
      <div className="cursor-demo-body">
        <aside>
          <small>RUNS</small>
          <button className="active"><span>Support handoff</span><em>now</em></button>
          <button><span>Patient summary</span><em>8m</em></button>
          <button><span>Finance workflow</span><em>21m</em></button>
          <small>POLICY</small>
          <p>Synthetic vault</p>
          <p>Raw values redacted</p>
        </aside>
        <section className="cursor-demo-trace">
          <header><span>Execution trace</span><code>4 events</code></header>
          <div className="cursor-event-list">
            {events.map(([index, channel, description, state], eventIndex) => (
              <article key={index} data-state={state} data-active={eventIndex === activeEvent}>
                <b>{index}</b>
                <div><code>{channel}</code><p>{description}</p></div>
                <span>{state === "leak" ? "exposed" : state}</span>
              </article>
            ))}
          </div>
        </section>
        <section className="cursor-demo-report">
          <header><span>AgentRisk</span><code>RI {riskIndex}</code></header>
          <div className="cursor-risk-score"><strong key={privacyScore}>{privacyScore}</strong><span>/ 100<br />privacy score</span></div>
          <div className="cursor-risk-bar"><i style={{ width: `${100 - privacyScore}%` }} /></div>
          <dl>
            <div><dt>Boundary</dt><dd>{activeEvent === 0 ? "Monitoring" : "Failed"}</dd></div>
            <div><dt>Distinct leaks</dt><dd>{activeEvent === 0 ? 0 : activeEvent === 1 ? 1 : 2}</dd></div>
            <div><dt>Affected channels</dt><dd>{activeEvent === 0 ? "0 / 6" : activeEvent === 1 ? "1 / 6" : "2 / 6"}</dd></div>
          </dl>
          <button>Open remediation plan <Arrow /></button>
        </section>
      </div>
    </div>
  )
}

function FlowDemo() {
  const [activeStep, setActiveStep] = useState(0)
  const reducedMotion = usePrefersReducedMotion()
  const steps = [
    ["Customer record", "Source", "Authorized input"],
    ["Support agent", "Processing", "Private context"],
    ["Shared memory", "Exposure", "Email + account ID"],
    ["Final answer", "Clean", "No sensitive values"],
  ]

  useEffect(() => {
    if (reducedMotion) return
    const timer = window.setInterval(() => setActiveStep((current) => (current + 1) % steps.length), 1900)
    return () => window.clearInterval(timer)
  }, [reducedMotion, steps.length])

  return (
    <div className="cursor-flow-demo">
      <div className="cursor-flow-head"><span>customer-support.run</span><b><i /> tracing live</b></div>
      {steps.map(([title, status, detail], index) => (
        <div className="cursor-flow-row" data-active={index === activeStep} data-leak={status === "Exposure"} key={title}>
          <span>{String(index + 1).padStart(2, "0")}</span>
          <div><strong>{title}</strong><small>{detail}</small></div>
          <b>{status}</b>
        </div>
      ))}
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
            <div className="cursor-actions">
              <Link className="cursor-button cursor-button-dark" to="/register">Run your first audit <Arrow /></Link>
              <Link className="cursor-button cursor-button-light" to="/docs">Read the documentation <Arrow /></Link>
            </div>
          </div>
          <ProductDemo />
        </section>

        <section className="cursor-trust">
          <h2>Works with the agent frameworks and protocols you already use</h2>
          <div className="cursor-integration-grid">{integrations.map((integration, index) => <span key={integration}><i>{String(index + 1).padStart(2, "0")}</i><b>{integration}</b></span>)}</div>
          <p>Compatibility, not customer endorsement. Framework adapters and generic trace ingestion use the same AgentLeak schema.</p>
        </section>

        <section className="cursor-feature cursor-feature-lead" id="workflow">
          <div className="cursor-feature-copy">
            <p className="cursor-eyebrow">Complete trace analysis</p>
            <h2>The final output can be clean while the system is leaking.</h2>
            <p>AgentLeak follows sensitive values through the complete execution trace, reconstructs where exposure happened and shows the exact channel that crossed policy.</p>
            <Link to="/docs">Understand the trace model <Arrow /></Link>
          </div>
          <FlowDemo />
        </section>

        <section className="cursor-feature-grid">
          <article>
            <div>
              <p className="cursor-eyebrow">AgentRisk</p>
              <h3>A score your team can explain.</h3>
              <p>Severity-weighted risk from 0 to 1, normalized against the audited sensitive vault. No model decides the score.</p>
              <Link to="/docs#agentrisk">Learn how scoring works <Arrow /></Link>
            </div>
            <PlatformWorkbench />
          </article>
          <article>
            <div>
              <p className="cursor-eyebrow">Built for autonomous agents</p>
              <h3>Agents can discover, test and improve themselves.</h3>
              <p>Machine-readable instructions, OpenAPI, scoped project keys and a bounded remediation loop work without a browser.</p>
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
