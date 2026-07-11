import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Grain, SignalField } from "@/features/SignalField"

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false)
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)")
    setReduced(mq.matches)
    const onChange = () => setReduced(mq.matches)
    mq.addEventListener("change", onChange)
    return () => mq.removeEventListener("change", onChange)
  }, [])
  return reduced
}

const channels = ["tool_call", "shared_memory", "agent_message", "log", "generated_file", "final_output"]

/** Small, bespoke node-path glyphs — one per scenario, hand-placed to echo the
 * data path already named in copy (e.g. "CRM lookup → handoff → ticket") with
 * the node where the leak actually surfaces picked out in the accent color. */
const SCENARIO_GLYPHS: { nodes: [number, number][]; leak: number }[] = [
  { nodes: [[7, 30], [28, 11], [49, 27]], leak: 1 }, // support: leak at the internal handoff
  { nodes: [[7, 13], [28, 32], [49, 15]], leak: 1 }, // healthcare: leak at the summary agent
  { nodes: [[7, 28], [28, 8], [49, 30]], leak: 1 }, // finance: leak at the risk agent
  { nodes: [[7, 8], [7, 20], [7, 32], [45, 20]], leak: 3 }, // multi-agent: leak at shared memory hub
]

function ScenarioGlyph({ index }: { index: number }) {
  const g = SCENARIO_GLYPHS[index % SCENARIO_GLYPHS.length]
  const [lx, ly] = g.nodes[g.leak]
  return (
    <svg className="al-scenario-glyph" viewBox="0 0 56 40" aria-hidden="true">
      {g.nodes.slice(1).map(([x, y], i) => {
        const [px, py] = g.nodes[i]
        return <line key={i} x1={px} y1={py} x2={x} y2={y} />
      })}
      {g.nodes.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={i === g.leak ? 3.2 : 2.2} className={i === g.leak ? "al-glyph-leak" : undefined} />
      ))}
      <circle cx={lx} cy={ly} r={7} className="al-glyph-pulse" style={{ animationDelay: `${index * 0.6}s` }} />
    </svg>
  )
}

function Wordmark({ light = false }: { light?: boolean }) {
  return (
    <Link to="/" className={`al-wordmark ${light ? "text-[#0a0a0a]" : "text-[#f1f1ed]"}`} aria-label="AgentLeak home">
      <span className="al-mark" aria-hidden="true"><i /><i /><i /></span>
      <span>AgentLeak</span><b>/</b>
    </Link>
  )
}

function BracketLink({ to, children, inverted = false }: { to: string; children: React.ReactNode; inverted?: boolean }) {
  const className = `al-bracket-link ${inverted ? "al-bracket-link-dark" : ""}`
  if (to.startsWith("/")) return <Link to={to} className={className}><span>[</span>{children}<span>]</span></Link>
  return <a href={to} className={className}><span>[</span>{children}<span>]</span></a>
}

const TRACE_PATH = "M-40 270 C 100 230, 124 70, 270 118 S 428 322, 568 224 S 700 50, 940 92"
// Color the traveling packet cool-clean → warm-leak → cool-clean, timed to
// cross "warm" right where the map calls out EXPOSURE / PROPAGATED below.
const PACKET_COLOR_KEYTIMES = "0; 0.22; 0.34; 0.62; 0.76; 1"
const PACKET_COLORS = "#f1f1ed; #f1f1ed; #ff6a3d; #ff6a3d; #f1f1ed; #f1f1ed"

function TracePacket({ delay }: { delay: number }) {
  return (
    <>
      <circle r="7" className="al-packet-glow" opacity="0.35">
        <animateMotion dur="5.2s" begin={`${delay}s`} repeatCount="indefinite" rotate="auto">
          <mpath href="#al-trace-line" />
        </animateMotion>
        <animate attributeName="fill" values={PACKET_COLORS} keyTimes={PACKET_COLOR_KEYTIMES} dur="5.2s" begin={`${delay}s`} repeatCount="indefinite" />
      </circle>
      <circle r="2.6" className="al-packet">
        <animateMotion dur="5.2s" begin={`${delay}s`} repeatCount="indefinite" rotate="auto">
          <mpath href="#al-trace-line" />
        </animateMotion>
        <animate attributeName="fill" values={PACKET_COLORS} keyTimes={PACKET_COLOR_KEYTIMES} dur="5.2s" begin={`${delay}s`} repeatCount="indefinite" />
      </circle>
    </>
  )
}

function TraceInstrument() {
  const reduceMotion = usePrefersReducedMotion()
  return (
    <div className="al-instrument" aria-label="A trace crossing internal agent channels before reaching a clean final output">
      <div className="al-instrument-head"><span>TRACE / RUN_2048</span><span>LIVE ANALYSIS</span></div>
      <div className="al-trace-map">
        <svg viewBox="0 0 900 360" role="img" aria-label="Sensitive data path through an agent run">
          <defs><filter id="soft"><feGaussianBlur stdDeviation="16" /></filter></defs>
          <path className="al-glow" d={TRACE_PATH} filter="url(#soft)" />
          <path id="al-trace-line" className="al-path al-path-ghost" d={TRACE_PATH} />
          <path className="al-path al-path-live" d={TRACE_PATH} />
          <g className="al-nodes"><circle cx="145" cy="173" r="4" /><circle cx="325" cy="162" r="4" /><circle cx="554" cy="233" r="4" /><circle cx="743" cy="100" r="4" /></g>
          {!reduceMotion && (
            <g className="al-packets"><TracePacket delay={0} /><TracePacket delay={-1.7} /><TracePacket delay={-3.5} /></g>
          )}
        </svg>
        <div className="al-map-label al-map-one"><small>01</small><span>INPUT</span><b>PII DETECTED</b></div>
        <div className="al-map-label al-map-two"><small>02</small><span>TOOL CALL</span><b>EXPOSURE</b></div>
        <div className="al-map-label al-map-three"><small>03</small><span>SHARED MEMORY</span><b>PROPAGATED</b></div>
        <div className="al-map-label al-map-four"><small>04</small><span>FINAL OUTPUT</span><b>CLEAN</b></div>
      </div>
      <div className="al-instrument-foot"><span>RISK INDEX / 0.38</span><span>POLICY / BLOCKED</span><span>RAW VALUES / NOT STORED</span></div>
    </div>
  )
}

export function Landing() {
  return (
    <div className="landing bg-[#080909] text-[#f1f1ed]">
      <Grain />
      <header className="al-header">
        <Wordmark />
        <nav aria-label="Main navigation">
          <a href="#system"><span>System</span><b>01</b></a>
          <a href="#scenarios"><span>Scenarios</span><b>02</b></a>
          <a href="#evidence"><span>Evidence</span><b>03</b></a>
          <Link to="/docs"><span>Docs</span><b>04</b></Link>
        </nav>
        <div className="al-header-actions"><BracketLink to="/login">Sign in</BracketLink><BracketLink to="/register">Run an audit</BracketLink></div>
      </header>

      <main>
        <section className="al-hero">
          <SignalField />
          <div className="al-hero-copy">
            <p className="al-kicker">PRIVACY TESTING FOR AGENT SYSTEMS // OPEN SOURCE</p>
            <h1><span>The output</span><span>is not the trace.</span></h1>
            <p className="al-lede">AgentLeak reveals where sensitive data travels inside single-agent and multi-agent systems — across tools, memory, messages, logs and files.</p>
            <div className="al-hero-links"><BracketLink to="/register">Start local audit</BracketLink><BracketLink to="/docs">Read the docs</BracketLink></div>
          </div>
          <div className="al-hero-meta"><span>BUILT FOR AGENTS</span><span>NO TELEMETRY</span><span>JUL // 2026</span></div>
        </section>

        <section className="al-intro" id="system">
          <div className="al-section-label">01 // SYSTEM</div>
          <div className="al-intro-body">
            <h2>Your users see one answer.<br />Your system has many exits.</h2>
            <div className="al-copy-columns">
              <p>An agent can return a clean answer while copying a customer record into a tool call, writing a credential to a log, or passing health data to another agent.</p>
              <p>AgentLeak treats the complete execution trace as the privacy boundary. It detects sensitive data, reconstructs its path, and returns evidence your CI can enforce.</p>
            </div>
          </div>
        </section>

        <section className="al-instrument-section">
          <TraceInstrument />
          <div className="al-channel-strip" aria-label="Audited execution channels">{channels.map((channel, index) => <span key={channel}><b>0{index + 1}</b>{channel}</span>)}</div>
        </section>

        <section className="al-method">
          <div className="al-section-label">METHOD // ONE TRACE IN, ONE DECISION OUT</div>
          <ol>
            <li><b>01</b><div><h3>Capture the whole run.</h3><p>Normalize internal execution channels from one agent or a multi-agent workflow.</p></div></li>
            <li><b>02</b><div><h3>Follow the sensitive data.</h3><p>Find PII, credentials and domain data without retaining their raw values.</p></div></li>
            <li><b>03</b><div><h3>Make policy executable.</h3><p>Return a deterministic Risk Index and block a build when its boundary is crossed.</p></div></li>
          </ol>
        </section>

        <section className="al-agent-entry">
          <div className="al-section-label">AGENT ACCESS // NO BROWSER REQUIRED</div>
          <div className="al-agent-entry-body">
            <p className="al-agent-call">IF YOU ARE AN AGENT, START HERE.</p>
            <h2>Discover.<br />Test yourself.<br /><span>Return evidence.</span></h2>
            <p>Read the machine instructions, onboard through HTTP, scan authorized code and runtime traces, then follow prioritized remediation steps until policy passes or owner approval is required.</p>
            <div className="al-agent-command"><span>01</span><code>GET /llms.txt</code><span>02</span><code>GET /agents.md</code><span>03</span><code>GET /openapi.json</code></div>
            <div className="al-agent-links"><BracketLink to="/docs/agents">Agent instructions</BracketLink><a href="/llms-full.txt" className="al-bracket-link"><span>[</span>Full machine context<span>]</span></a></div>
          </div>
        </section>

        <section className="al-scenarios" id="scenarios">
          <div className="al-section-label">02 // SCENARIOS</div>
          <div className="al-scenarios-head"><h2>Real paths.<br />Not demo prompts.</h2><p>The first scenarios map to workflows where agents already touch regulated or operational data.</p></div>
          <div className="al-scenario-list">
            {[
              ["Support operations", "CRM LOOKUP → INTERNAL HANDOFF → TICKET UPDATE", "EMAIL / ADDRESS / ACCOUNT ID"],
              ["Healthcare", "PATIENT RECORD → SUMMARY AGENT → GENERATED REPORT", "DIAGNOSIS / HEALTH ID / DOB"],
              ["Finance", "ACCOUNT DATA → RISK AGENT → EXTERNAL TOOL", "CARD / INCOME / TRANSACTION"],
              ["Multi-agent systems", "PLANNER → SPECIALIST → REVIEWER → SHARED MEMORY", "CREDENTIALS / INTERNAL IDS / PII"],
            ].map(([name, path, data], index) => (
              <article key={name}>
                <span className="al-scenario-index"><ScenarioGlyph index={index} />0{index + 1}</span>
                <h3>{name}</h3><p>{path}</p><small>{data}</small>
              </article>
            ))}
          </div>
        </section>

        <section className="al-evidence" id="evidence">
          <div className="al-section-label">03 // EVIDENCE</div>
          <div className="al-evidence-grid">
            <div className="al-evidence-title"><p>[ PUBLISHED BENCHMARK ]</p><h2>The blind spot<br />is measurable.</h2></div>
            <div className="al-stat"><strong>41.7<sup>%</sup></strong><p>of violations were missed by output-only auditing in the published benchmark.</p></div>
            <div className="al-stat"><strong>4,979</strong><p>traces across five models and four sensitive domains in the research evaluation.</p></div>
          </div>
          <div className="al-positioning"><p><b>THE CATEGORY EXISTS.</b> Runtime guardrails, agent security and red-team platforms solve adjacent problems.</p><p><b>THE WEDGE IS SPECIFIC.</b> Local, open-source privacy tests for internal multi-agent data paths, with deterministic CI evidence.</p><p><b>THE CLAIM IS BOUNDED.</b> A passing test is evidence for the tested trace and policy — not a universal security guarantee.</p></div>
        </section>

        <section className="al-cta">
          <div><p>READY // LOCAL FIRST</p><h2>Inspect what happens<br />before the answer.</h2></div>
          <div><p>Create a workspace, run a bundled scenario, then connect one real agent when the baseline makes sense.</p><BracketLink to="/register" inverted>Create local workspace</BracketLink></div>
        </section>
      </main>

      <footer className="al-footer"><Wordmark light /><p>LOCAL PRIVACY TESTING FOR AGENT SYSTEMS.</p><span><Link to="/docs">DOCS</Link> // OSS // 2026</span></footer>
    </div>
  )
}
