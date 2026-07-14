import { useEffect, useState } from "react"
import type { RunSummary } from "@/lib/api"

export function usePrefersReducedMotion() {
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

export function Arrow() {
  return <span aria-hidden="true">→</span>
}

// Faithful miniature of a real run report (pages/RunView): per-channel risk,
// concrete findings with severity levels, and the remediation hint an agent
// can act on, the artifact you actually get from an analysis.
export const REPORT_CHANNELS = [
  ["user_input", "Customer message received", "clean", ""],
  ["tool_call", "email + account_id sent to calendar.create", "L3", "EMAIL · ACCOUNT_ID"],
  ["shared_memory", "account_id persisted for the next agent", "L2", "ACCOUNT_ID"],
  ["log", "No sensitive values written", "clean", ""],
  ["final_output", "Clean answer to the customer", "clean", ""],
] as const

export function RunReportDemo({ compact = false }: { compact?: boolean }) {
  const [activeRow, setActiveRow] = useState(1)
  const reducedMotion = usePrefersReducedMotion()

  useEffect(() => {
    if (reducedMotion) return
    const timer = window.setInterval(() => setActiveRow((current) => (current + 1) % REPORT_CHANNELS.length), 2000)
    return () => window.clearInterval(timer)
  }, [reducedMotion])

  return (
    <div className="cursor-report" data-compact={compact} aria-label="A real AgentLeak run report: channel risks, findings and the remediation hint">
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
        <button
          type="button"
          className="cursor-report-row"
          data-active={index === activeRow}
          data-leak={level !== "clean"}
          key={channel}
          onClick={() => setActiveRow(index)}
        >
          <code>{channel}</code>
          <div><strong>{description}</strong>{types && <small>{types}</small>}</div>
          <b>{level === "clean" ? "clean" : level}</b>
        </button>
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

export function PlatformWorkbench() {
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
export function CIGateDemo() {
  const [open, setOpen] = useState(true)
  return (
    <div className="cursor-ci" aria-label="AgentLeak as a required CI status check that blocks a merge">
      <div className="cursor-ci-head"><b>feat: multi-agent claims workflow</b><small>#428 opened by claims-reviewer</small></div>
      <div className="cursor-ci-body">
        <div className="cursor-ci-check" data-state="ok"><i /><span>build</span><em>passed</em></div>
        <div className="cursor-ci-check" data-state="ok"><i /><span>unit tests</span><em>passed</em></div>
        <button type="button" className="cursor-ci-check" data-state="fail" onClick={() => setOpen((value) => !value)}>
          <i /><span>AgentLeak / privacy-gate</span><em>{open ? "failed · hide" : "failed · details"}</em>
        </button>
        {open && (
          <div className="cursor-ci-detail">
            <p><b>shared_memory</b> leaked <code>account_id</code> at level <b>L3</b>, above the project policy (L2).</p>
            <p>Risk Index 0.38 · privacy score 62 / 100</p>
          </div>
        )}
        <div className="cursor-ci-check" data-state="ok"><i /><span>e2e</span><em>passed</em></div>
      </div>
      <div className="cursor-ci-foot"><b data-blocked="true">Merge blocked</b><span>1 required check failed</span></div>
    </div>
  )
}

// A terminal that reads like the real install path: pip / docker, MIT, local.
export function OpenSourceDemo() {
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

export function AgentTerminal() {
  return (
    <div className="cursor-terminal"><div><span /><span /><span /></div><code><span><i>$</i> curl agents.fomox.com/llms.txt</span><span><i>$</i> POST /api/agent/onboard</span><span><b>project created</b></span><span><i>$</i> POST /api/selftest</span><span><em>2 exposures · policy failed</em></span></code></div>
  )
}

const TRACE_EVENTS = [
  { channel: "tool_response", time: "09:41:02.118", title: "crm.lookup returned customer record", detail: "Source: account_id, email and plan entered the reachable vault.", level: "source" },
  { channel: "tool_call", time: "09:41:02.604", title: "calendar.create received account_id", detail: "Disclosure: an identifier crossed into a third-party tool argument.", level: "L3" },
  { channel: "shared_memory", time: "09:41:02.817", title: "account_id persisted for claims-reviewer", detail: "Disclosure: sensitive context outlived the current agent turn.", level: "L3" },
  { channel: "final_output", time: "09:41:03.201", title: "Customer-facing answer is clean", detail: "No sensitive value appears in the final response.", level: "clean" },
] as const

export function TraceExplorerDemo() {
  const [active, setActive] = useState(1)
  const event = TRACE_EVENTS[active]

  return (
    <div className="product-view product-trace" aria-label="Interactive trace explorer showing a leak path across internal agent channels">
      <header className="product-view-bar">
        <div><span /><span /><span /></div>
        <p><b>support-router</b><em>/</em>run_2048.trace</p>
        <strong>RI 0.38 · failed</strong>
      </header>
      <div className="product-trace-body">
        <aside className="product-rail">
          <small>EXPLORER</small>
          <b>run_2048</b>
          <span>Summary <i>1</i></span>
          <span data-active="true">Execution trace <i>4</i></span>
          <span>Leak paths <i>2</i></span>
          <span>Findings <i>2</i></span>
          <small>CHANNELS</small>
          <span>Tools</span><span>Memory</span><span>Messages</span><span>Output</span>
        </aside>
        <section className="product-trace-timeline">
          <header><div><b>Execution trace</b><small>4 events · 2 disclosures</small></div><span>All channels</span></header>
          <div className="product-trace-events">
            {TRACE_EVENTS.map((item, index) => (
              <button key={item.time} type="button" data-active={active === index} data-level={item.level} aria-pressed={active === index} onClick={() => setActive(index)}>
                <i>{index + 1}</i>
                <code>{item.time}</code>
                <div><b>{item.channel}</b><span>{item.title}</span></div>
                <em>{item.level}</em>
              </button>
            ))}
          </div>
          <div className="product-flow-line"><span>source</span><i /><b>tool_call</b><i /><b>shared_memory</b><i /><span>clean output</span></div>
        </section>
        <aside className="product-inspector">
          <header><b>Event inspector</b><span>{active + 1} / 4</span></header>
          <dl><div><dt>Channel</dt><dd>{event.channel}</dd></div><div><dt>Classification</dt><dd data-hot={event.level.startsWith("L")}>{event.level}</dd></div></dl>
          <section><small>WHY IT MATTERS</small><p>{event.detail}</p></section>
          <section><small>EVIDENCE, REDACTED</small><code>account_id: &quot;acct_••••7F2&quot;</code></section>
          <section data-fix="true"><small>REMEDIATION</small><p>Apply channel redaction before persistence, then replay this trace to verify the leak path is closed.</p></section>
        </aside>
      </div>
    </div>
  )
}

const RISK_SCENARIOS = [
  { name: "support-router", risk: "0.18", privacy: "82", leaks: "1", status: "Pass" },
  { name: "claims-reviewer", risk: "0.38", privacy: "62", leaks: "2", status: "Review" },
  { name: "patient-summary", risk: "0.64", privacy: "36", leaks: "4", status: "Fail" },
] as const

export function RiskModelDemo() {
  const [active, setActive] = useState(1)
  const scenario = RISK_SCENARIOS[active]

  return (
    <div className="product-view product-risk" aria-label="AgentRisk scoring laboratory comparing deterministic scores across agent runs">
      <header className="product-view-bar"><div><span /><span /><span /></div><p><b>AgentRisk lab</b><em>/</em>scoring model</p><strong>deterministic</strong></header>
      <div className="product-risk-body">
        <aside className="product-rail">
          <small>RUN SET</small>
          {RISK_SCENARIOS.map((item, index) => <button key={item.name} type="button" data-active={active === index} aria-pressed={active === index} onClick={() => setActive(index)}><b>{item.name}</b><span>RI {item.risk}</span></button>)}
          <small>MODEL</small><span data-active="true">AgentRisk v1</span><span>Level weights</span><span>Vault coverage</span>
        </aside>
        <section className="product-risk-main">
          <header><div><small>SELECTED RUN</small><h4>{scenario.name}</h4></div><span data-status={scenario.status}>{scenario.status}</span></header>
          <div className="product-risk-score"><div><small>Risk Index</small><strong>{scenario.risk}</strong><span>0 safer <i><b style={{ width: `${Number(scenario.risk) * 100}%` }} /></i> 1 exposed</span></div><div><small>Privacy score</small><strong>{scenario.privacy}</strong><span>/ 100</span></div><div><small>Distinct leaks</small><strong>{scenario.leaks}</strong><span>occurrences deduplicated</span></div></div>
          <section className="product-risk-formula"><header><b>How this number is produced</b><span>No model judge</span></header><div><code>RI = WSL / ρ<sub>S</sub></code><p><b>WSL</b> sums the severity weights of distinct leaked secrets. <b>ρ<sub>S</sub></b> is the weighted sensitive vault reachable in this run.</p></div></section>
          <section className="product-risk-matrix"><header><span>Finding</span><span>Level</span><span>Weight</span><span>Channel</span></header><div><b>account_id</b><em>L3</em><code>3</code><span>shared_memory</span></div><div><b>email</b><em>L2</em><code>2</code><span>tool_call</span></div><footer><span>Same trace + same vault</span><b>same score, every run</b></footer></section>
        </section>
      </div>
    </div>
  )
}

const CI_STEPS = ["Checkout", "Unit tests", "Agent trace", "Privacy gate", "Deploy"] as const

export function PipelineGateDemo() {
  const [active, setActive] = useState(3)

  return (
    <div className="product-view product-pipeline" aria-label="CI pipeline with a privacy policy gate and contextual remediation">
      <header className="product-view-bar"><div><span /><span /><span /></div><p><b>release-42</b><em>/</em>privacy pipeline</p><strong>merge blocked</strong></header>
      <div className="product-pipeline-body">
        <aside className="product-pipeline-list">
          <header><b>Workflow run #428</b><small>feat/multi-agent-claims</small></header>
          {CI_STEPS.map((step, index) => <button type="button" key={step} data-active={active === index} data-state={index < 3 ? "ok" : index === 3 ? "fail" : "waiting"} aria-pressed={active === index} onClick={() => setActive(index)}><i>{index < 3 ? "✓" : index === 3 ? "!" : "·"}</i><span>{step}<small>{index < 3 ? "completed" : index === 3 ? "policy failed" : "waiting"}</small></span><em>{index + 1}</em></button>)}
        </aside>
        <section className="product-pipeline-log">
          <header><b>{CI_STEPS[active]}</b><span>{active === 3 ? "exit code 1" : active < 3 ? "passed" : "queued"}</span></header>
          {active === 3 ? <><div className="pipeline-command"><code>$ agentleak run --trace artifacts/claims.json --config agentleak.yaml --fail-under 80</code><span>Analyzing 18 events across 6 channels...</span><b>Policy boundary crossed</b></div><div className="pipeline-finding"><header><span>L3</span><b>account_id disclosed through shared_memory</b></header><p>Project policy allows this channel up to L2. The final output is clean, but the claims-reviewer can read the persisted identifier.</p><dl><div><dt>Risk Index</dt><dd>0.38</dd></div><div><dt>Privacy</dt><dd>62 / 100</dd></div><div><dt>Action</dt><dd>block merge</dd></div></dl></div></> : <div className="pipeline-empty"><i>{active < 3 ? "✓" : "·"}</i><b>{active < 3 ? `${CI_STEPS[active]} completed` : "Waiting for the privacy gate"}</b><span>Select Privacy gate to inspect the policy decision.</span></div>}
        </section>
        <aside className="product-pipeline-policy"><header><b>Policy inspector</b><span>agentleak.yaml</span></header><code><span>gate:</span><b>  fail_on:</b><em> L3</em><b>  channels:</b><em> shared_memory</em><b>  privacy_score:</b><em> 80</em></code><section><small>SUGGESTED PATCH</small><p>Redact identifiers before writing cross-agent memory.</p><code>memory.write(redact(context))</code></section><footer><b>Required check</b><span>Prevents deploy until clean</span></footer></aside>
      </div>
    </div>
  )
}

export function AgentLoopDemo() {
  const [active, setActive] = useState(2)
  const stages = ["Discover", "Onboard", "Self-test", "Apply fix", "Verify"] as const
  const stageContent = [
    { actor: "agent", action: "GET /.well-known/agent-card.json", result: "capabilities: [selftest, improve, code_scan]", note: "Discovery exposes endpoints and input schemas." },
    { actor: "agent", action: "POST /api/agent/onboard", result: "project created · scoped key issued", note: "The key is limited to this project and quota." },
    { actor: "agent", action: "POST /api/selftest · 18 events", result: "passed: false · privacy_score: 62", note: "hint: redact account_id before shared_memory" },
    { actor: "agent", action: "edit memory_adapter.py", result: "memory.write(redact(context))", note: "One bounded patch addresses the reported channel." },
    { actor: "agent", action: "POST /api/selftest · replay run_2048", result: "passed: true · privacy_score: 100", note: "delta: +38 · disclosure path closed" },
  ] as const
  const current = stageContent[active]

  return (
    <div className="product-view product-loop" aria-label="Autonomous agent self-test and remediation loop">
      <header className="product-view-bar"><div><span /><span /><span /></div><p><b>support-bot</b><em>/</em>autonomous privacy loop</p><strong>iteration 02</strong></header>
      <div className="product-loop-body">
        <aside className="product-loop-stages"><small>AGENT LOOP</small>{stages.map((stage, index) => <button key={stage} type="button" data-active={active === index} data-done={index < active} aria-pressed={active === index} onClick={() => setActive(index)}><i>{index < active ? "✓" : index + 1}</i><span>{stage}</span></button>)}<footer><span>Scoped key</span><code>ak_••••91d</code></footer></aside>
        <section className="product-loop-console"><header><span>{stages[active]}</span><em>machine-readable</em></header><code><span><i>{current.actor}</i> {current.action}</span><span><b>agentleak</b> {current.result}</span><span><em>context</em> {current.note}</span><span><i>policy</i> project: support-bot · trace: run_2048</span><span><b>agentleak</b> {active < stages.length - 1 ? `next: ${stages[active + 1].toLowerCase()}` : "loop complete · policy passed"}</span></code><div className="product-loop-progress">{stages.map((stage, index) => <span key={stage} data-active={active === index} data-done={index < active}>{stage.toLowerCase()}</span>)}</div></section>
        <aside className="product-loop-diff"><header><b>Structured remediation</b><span>JSON</span></header><dl><div><dt>priority</dt><dd>high</dd></div><div><dt>channel</dt><dd>shared_memory</dd></div><div><dt>data_types</dt><dd>account_id</dd></div></dl><section><small>PATCH</small><code><del>- memory.write(context)</del><ins>+ memory.write(redact(context))</ins></code></section><footer><div><small>Before</small><b>62</b></div><span>→</span><div><small>Expected</small><b>100</b></div></footer></aside>
      </div>
    </div>
  )
}
