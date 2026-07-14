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
