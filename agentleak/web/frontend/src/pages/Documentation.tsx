import { Link } from "react-router-dom"

type Audience = "overview" | "developers" | "agents"

const BASE = "https://agents.fomox.com"
const INSTALL = [
  "pip install agentleak",
  "agentleak init",
  "agentleak run --scenario healthcare_patient_summary",
  "",
  "# With the local web interface",
  "pip install 'agentleak[gui]'",
  "agentleak serve",
].join("\n")
const TRACE = [
  "{",
  '  "run_id": "run_001",',
  '  "agent_name": "support-bot",',
  '  "events": [',
  '    {"channel":"tool_call", "source":"agent", "target":"crm",',
  '     "content":{"email":"canary@example.test"}},',
  '    {"channel":"final_output", "source":"agent", "target":"user",',
  '     "content":"Ticket updated"}',
  "  ]",
  "}",
].join("\n")
const SDK = [
  "from agentleak import AgentLeakRunner, Trace",
  "",
  'trace = Trace(run_id="demo", agent_name="support-bot")',
  "trace.add_event(",
  '    channel="tool_call", source="agent", target="crm",',
  '    content={"email": "canary@example.test"},',
  ")",
  'trace.add_event(channel="final_output", content="Done")',
  "",
  "result = AgentLeakRunner().analyze(trace)",
  "print(result.risk_index, result.verdict)",
].join("\n")
const CI = [
  "# agentleak exits non-zero below the threshold",
  "agentleak run --trace traces/latest.json --fail-under 70",
  "",
  "# GitHub Actions",
  "- name: Agent privacy gate",
  "  run: agentleak run --trace traces/latest.json --fail-under 70",
].join("\n")
const ONBOARD = [
  "curl -sS -X POST " + BASE + "/api/agent/onboard \\",
  "  -H 'content-type: application/json' \\",
  "  -d '{\"email\":\"owner@example.com\",\"agent_name\":\"SupportBot\"}'",
].join("\n")

function DocWordmark() {
  return <Link to="/" className="docs-wordmark" aria-label="AgentLeak home"><span>AgentLeak</span><b>/</b><em>DOCS</em></Link>
}

function Code({ children }: { children: string }) {
  return <pre className="docs-code"><code>{children}</code></pre>
}

function DocHeader({ audience }: { audience: Audience }) {
  return (
    <header className="docs-header">
      <DocWordmark />
      <nav aria-label="Documentation audiences">
        <Link className={audience === "overview" ? "active" : ""} to="/docs">Overview</Link>
        <Link className={audience === "developers" ? "active" : ""} to="/docs/developers">For developers</Link>
        <Link className={audience === "agents" ? "active" : ""} to="/docs/agents">For agents</Link>
      </nav>
      <div className="docs-header-actions"><a href="/api/docs">API</a><Link to="/register">[ RUN AN AUDIT ]</Link></div>
    </header>
  )
}

function DocRail({ audience }: { audience: Audience }) {
  const items = audience === "agents"
    ? [["start", "Start"], ["rules", "Operating rules"], ["loop", "Improvement loop"], ["errors", "Failure handling"], ["binding", "REST binding"]]
    : audience === "developers"
      ? [["start", "Install"], ["trace", "Trace model"], ["sdk", "SDK"], ["integrations", "Integrations"], ["ci", "CI gate"], ["api", "Cloud API"]]
      : [["model", "Mental model"], ["paths", "Choose a path"], ["channels", "Channels"], ["scoring", "Scoring"], ["safety", "Safety boundary"]]
  return (
    <aside className="docs-rail">
      <p>ON THIS PAGE</p>
      <nav>{items.map(([id, label], index) => <a key={id} href={"#" + id}><b>0{index + 1}</b>{label}</a>)}</nav>
      <div className="docs-rail-machine"><span>MACHINE ACCESS</span><a href="/llms.txt">llms.txt</a><a href="/agents.md">agents.md</a><a href="/openapi.json">openapi.json</a></div>
    </aside>
  )
}

function Overview() {
  return (
    <>
      <section className="docs-lead" id="model"><p className="docs-eyebrow">DOCUMENTATION // START HERE</p><h1>See the run.<br /><span>Not only the answer.</span></h1><p>AgentLeak is a privacy test harness for agent systems. It follows sensitive data through every internal execution channel, shows exactly where it escaped, and turns the result into a policy decision.</p></section>
      <section className="docs-section"><p className="docs-index">01 // MENTAL MODEL</p><div><h2>One trace in.<br />One auditable decision out.</h2><p>A trace is an ordered record of what an agent received, called, shared, wrote and returned. AgentLeak detects sensitive values, builds the inventory exposed to the system, then measures which values crossed an unauthorized boundary.</p><div className="docs-flow"><span>TRACE</span><b>→</b><span>DETECT</span><b>→</b><span>FOLLOW</span><b>→</b><span>SCORE</span><b>→</b><span>GATE</span></div></div></section>
      <section className="docs-section" id="paths"><p className="docs-index">02 // CHOOSE A PATH</p><div className="docs-paths"><Link to="/docs/developers"><small>FOR DEVELOPERS</small><h3>Instrument your system.</h3><p>Install the SDK, capture a trace from any framework, run it locally, and fail CI on regression.</p><span>[ OPEN DEVELOPER GUIDE ]</span></Link><Link to="/docs/agents"><small>FOR AUTONOMOUS AGENTS</small><h3>Test yourself.</h3><p>Discover the API, onboard without a browser, scan code, follow remediation steps, and report the result.</p><span>[ OPEN AGENT PROTOCOL ]</span></Link></div></section>
      <section className="docs-section" id="channels"><p className="docs-index">03 // CHANNELS</p><div><h2>The privacy boundary is the complete run.</h2><div className="docs-channel-grid">{["user_input", "tool_call", "tool_response", "inter_agent_message", "shared_memory", "log", "generated_file", "final_output"].map((channel, index) => <div key={channel}><b>0{index + 1}</b><code>{channel}</code></div>)}</div></div></section>
      <section className="docs-section" id="scoring"><p className="docs-index">04 // SCORING</p><div><h2>Risk is weighted by what actually leaked.</h2><div className="docs-definition"><div><strong>0—1</strong><p><b>Risk Index.</b> Higher means a larger severity-weighted share of the sensitive inventory escaped.</p></div><div><strong>100—0</strong><p><b>Privacy score.</b> Human-readable inverse presentation of the same risk.</p></div><div><strong>L4—L1</strong><p><b>Finding level.</b> Critical, high, medium and low severity.</p></div></div></div></section>
      <section className="docs-section" id="safety"><p className="docs-index">05 // SAFETY BOUNDARY</p><div><h2>Evidence, not certification.</h2><p>A passing run proves that the tested trace met the configured policy. It does not prove that every future run is safe, replace legal review, or authorize an agent to upload production data. Use synthetic or canary values by default.</p></div></section>
    </>
  )
}

function Developers() {
  return (
    <>
      <section className="docs-lead" id="start"><p className="docs-eyebrow">DEVELOPER GUIDE // LOCAL FIRST</p><h1>Instrument once.<br /><span>Test every run.</span></h1><p>Use AgentLeak from the CLI, Python SDK, framework adapters, or the hosted HTTP API. The core analyzer runs locally with no required network calls.</p></section>
      <section className="docs-section"><p className="docs-index">01 // INSTALL</p><div><h2>Run your first test in minutes.</h2><Code>{INSTALL}</Code></div></section>
      <section className="docs-section" id="trace"><p className="docs-index">02 // TRACE MODEL</p><div><h2>Record events at system boundaries.</h2><p>Each event identifies a channel, source, target and content. Preserve ordering. Use stable agent and tool names so leak paths remain comparable across runs.</p><Code>{TRACE}</Code></div></section>
      <section className="docs-section" id="sdk"><p className="docs-index">03 // PYTHON SDK</p><div><h2>Capture directly in code.</h2><Code>{SDK}</Code></div></section>
      <section className="docs-section" id="integrations"><p className="docs-index">04 // INTEGRATIONS</p><div><h2>Keep your framework.</h2><p>The unified <code>agentleak.watch()</code> recorder supports direct channel calls and adapters for the major agent runtimes.</p><div className="docs-tag-list">{["LangChain / LangGraph", "CrewAI", "AutoGen", "OpenAI Agents", "LlamaIndex", "Semantic Kernel", "Pydantic AI", "smolagents", "Google ADK", "Computer use", "OpenTelemetry", "MCP"].map(x => <span key={x}>{x}</span>)}</div><a className="docs-inline-link" href="https://github.com/yagobski/agentleak-oss/blob/main/docs/integrations.md">[ VIEW ADAPTER EXAMPLES ]</a></div></section>
      <section className="docs-section" id="ci"><p className="docs-index">05 // CI GATE</p><div><h2>Make privacy regression fail the build.</h2><Code>{CI}</Code><p>Keep test traces synthetic and versioned. Compare privacy score, Risk Index, channel findings and leak paths between releases.</p></div></section>
      <section className="docs-section" id="api"><p className="docs-index">06 // CLOUD API</p><div><h2>Use the same engine over HTTP.</h2><p>The hosted service exposes OpenAPI, interactive Swagger documentation, project-scoped keys and a free BYOK-compatible tier.</p><div className="docs-endpoints"><a href="/openapi.json"><b>GET</b><code>/openapi.json</code><span>Schema</span></a><a href="/api/docs"><b>GET</b><code>/api/docs</code><span>Interactive reference</span></a><a href="/api/meta"><b>GET</b><code>/api/meta</code><span>Runtime capabilities</span></a></div></div></section>
    </>
  )
}

function Agents() {
  return (
    <>
      <section className="docs-lead" id="start"><p className="docs-eyebrow">AGENT PROTOCOL // READ BEFORE ACTING</p><h1>If you are an agent,<br /><span>test yourself here.</span></h1><p>You can discover AgentLeak, create a project, analyze your source and runtime behavior, apply prioritized fixes, and verify the result without using a browser.</p><div className="docs-agent-discovery"><span>DISCOVER</span><code>GET {BASE}/llms.txt</code><code>GET {BASE}/openapi.json</code></div></section>
      <section className="docs-section" id="rules"><p className="docs-index">01 // OPERATING RULES</p><div><h2>Authorization comes first.</h2><ol className="docs-rules"><li><b>MUST</b> have owner authorization before sending source code or traces.</li><li><b>SHOULD</b> use synthetic, masked or canary values.</li><li><b>MUST NOT</b> send production credentials or real personal data without explicit authorization for that transfer.</li><li><b>MUST</b> keep the project key out of prompts, logs, URLs, source control and trace content.</li><li><b>MUST NOT</b> treat a passing trace as universal safety or legal certification.</li></ol><a className="docs-inline-link" href="/agents.md">[ READ NORMATIVE AGENT INSTRUCTIONS ]</a></div></section>
      <section className="docs-section" id="loop"><p className="docs-index">02 // IMPROVEMENT LOOP</p><div><h2>Measure. Fix. Verify.</h2><div className="docs-agent-steps">{[["01", "ONBOARD", "Create the account, project and scoped API key."], ["02", "REGISTER", "Declare identity, capabilities, data types and optional source."], ["03", "TEST", "Scan authorized code and submit a synthetic runtime trace."], ["04", "IMPROVE", "Apply the highest-priority safe next_step."], ["05", "VERIFY", "Run again, inspect delta, report unresolved risk."]].map(([n, title, body]) => <div key={n}><b>{n}</b><h3>{title}</h3><p>{body}</p></div>)}</div><Code>{ONBOARD}</Code><p>Store the returned <code>api_key</code> securely. Send it as <code>X-AgentLeak-Key</code> on every later agent request.</p></div></section>
      <section className="docs-section" id="errors"><p className="docs-index">03 // FAILURE HANDLING</p><div><h2>Fail safely and predictably.</h2><div className="docs-error-table"><div><b>401</b><p>Stop. Request a valid project key; never guess credentials.</p></div><div><b>409</b><p>The account exists. Do not create variants to bypass ownership.</p></div><div><b>422</b><p>Repair the payload against OpenAPI, then retry once.</p></div><div><b>429</b><p>Honor <code>X-Quota-Reset</code> and back off. Never evade limits.</p></div><div><b>5xx</b><p>Use bounded exponential backoff and preserve idempotency.</p></div></div></div></section>
      <section className="docs-section" id="binding"><p className="docs-index">04 // AGENTLEAK REST BINDING</p><div><h2>Discovery-compatible. Transport-explicit.</h2><p id="agentleak-rest-binding">The well-known Agent Card declares a custom HTTP+JSON binding identified by this section. AgentLeak does not expose the standard A2A message/task transport. Use OpenAPI for request and response schemas.</p><div className="docs-endpoints"><a href="/.well-known/agent-card.json"><b>GET</b><code>/.well-known/agent-card.json</code><span>Capabilities</span></a><a href="/agents.md"><b>GET</b><code>/agents.md</code><span>Instructions</span></a><a href="/llms-full.txt"><b>GET</b><code>/llms-full.txt</code><span>Full context</span></a></div></div></section>
      <section className="docs-section"><p className="docs-index">05 // COMPLETION</p><div><h2>Return evidence to the owner.</h2><p>Your final report should include project ID, run ID, privacy score, Risk Index, pass/fail status, delta, remaining findings by severity, code-scan status and every action still requiring human approval. Never include raw secrets.</p></div></section>
    </>
  )
}

export function Documentation({ audience = "overview" }: { audience?: Audience }) {
  return (
    <div className="docs-shell">
      <DocHeader audience={audience} />
      <div className="docs-layout"><DocRail audience={audience} /><main>{audience === "developers" ? <Developers /> : audience === "agents" ? <Agents /> : <Overview />}</main></div>
      <footer className="docs-footer"><DocWordmark /><p>DOCUMENTATION FOR PEOPLE AND AGENTS.</p><Link to="/">[ BACK TO SYSTEM ]</Link></footer>
    </div>
  )
}
