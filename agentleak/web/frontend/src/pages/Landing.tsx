import { Link } from "react-router-dom"

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
  const events = [
    ["01", "tool_response", "CRM returned customer record", "source"],
    ["02", "tool_call", "Email forwarded to calendar", "leak"],
    ["03", "shared_memory", "Account ID copied to shared state", "leak"],
    ["04", "final_output", "Appointment confirmed", "clean"],
  ]

  return (
    <div className="cursor-demo" aria-label="AgentLeak trace analysis product preview">
      <div className="cursor-demo-bar">
        <div><span /><span /><span /></div>
        <p>AgentLeak / support-agent / run_2048</p>
        <b>Analysis complete</b>
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
            {events.map(([index, channel, description, state]) => (
              <article key={index} data-state={state}>
                <b>{index}</b>
                <div><code>{channel}</code><p>{description}</p></div>
                <span>{state === "leak" ? "exposed" : state}</span>
              </article>
            ))}
          </div>
        </section>
        <section className="cursor-demo-report">
          <header><span>AgentRisk</span><code>RI 0.38</code></header>
          <div className="cursor-risk-score"><strong>62</strong><span>/ 100<br />privacy score</span></div>
          <div className="cursor-risk-bar"><i /></div>
          <dl>
            <div><dt>Boundary</dt><dd>Failed</dd></div>
            <div><dt>Distinct leaks</dt><dd>2</dd></div>
            <div><dt>Affected channels</dt><dd>2 / 6</dd></div>
          </dl>
          <button>Open remediation plan <Arrow /></button>
        </section>
      </div>
    </div>
  )
}

const channels = ["Tools", "Memory", "Agent messages", "Logs", "Files", "Final output"]

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
            <p>Find sensitive data across tools, memory, inter-agent messages, logs and files. Get deterministic AgentRisk evidence you can act on and enforce in CI.</p>
            <div className="cursor-actions">
              <Link className="cursor-button cursor-button-dark" to="/register">Run your first audit <Arrow /></Link>
              <Link className="cursor-button cursor-button-light" to="/docs">Read the documentation <Arrow /></Link>
            </div>
          </div>
          <ProductDemo />
        </section>

        <section className="cursor-trust">
          <h2>One privacy boundary for every channel in an agent run</h2>
          <div>{channels.map((channel) => <span key={channel}>{channel}</span>)}</div>
        </section>

        <section className="cursor-feature cursor-feature-lead" id="workflow">
          <div className="cursor-feature-copy">
            <p className="cursor-eyebrow">Complete trace analysis</p>
            <h2>The final output can be clean while the system is leaking.</h2>
            <p>AgentLeak follows sensitive values through the complete execution trace, reconstructs where exposure happened and shows the exact channel that crossed policy.</p>
            <Link to="/docs">Understand the trace model <Arrow /></Link>
          </div>
          <div className="cursor-flow-demo">
            <div className="cursor-flow-head"><span>customer-support.run</span><b>4 boundaries</b></div>
            {[
              ["Customer record", "Source", "Authorized input"],
              ["Support agent", "Processing", "Private context"],
              ["Shared memory", "Exposure", "Email + account ID"],
              ["Final answer", "Clean", "No sensitive values"],
            ].map(([title, status, detail], index) => (
              <div className="cursor-flow-row" data-leak={status === "Exposure"} key={title}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div><strong>{title}</strong><small>{detail}</small></div>
                <b>{status}</b>
              </div>
            ))}
          </div>
        </section>

        <section className="cursor-feature-grid">
          <article>
            <div>
              <p className="cursor-eyebrow">AgentRisk</p>
              <h3>A score your team can explain.</h3>
              <p>Severity-weighted risk from 0 to 1, normalized against the audited sensitive vault. No model decides the score.</p>
              <Link to="/docs#agentrisk">Learn how scoring works <Arrow /></Link>
            </div>
            <div className="cursor-score-demo"><span>Risk index</span><strong>0.38</strong><i><b /></i><small>Privacy score 62 / 100</small></div>
          </article>
          <article>
            <div>
              <p className="cursor-eyebrow">Built for autonomous agents</p>
              <h3>Agents can discover, test and improve themselves.</h3>
              <p>Machine-readable instructions, OpenAPI, scoped project keys and a bounded remediation loop work without a browser.</p>
              <Link to="/docs/agents">Read agent instructions <Arrow /></Link>
            </div>
            <div className="cursor-terminal"><div><span /><span /><span /></div><code><i>$</i> curl agents.fomox.com/llms.txt<br /><i>$</i> POST /api/agent/onboard<br /><b>project created</b><br /><i>$</i> POST /api/selftest<br /><em>2 exposures · policy failed</em></code></div>
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
