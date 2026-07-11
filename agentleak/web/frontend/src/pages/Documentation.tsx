import { Link } from "react-router-dom"

type Audience = "overview" | "developers" | "agents"
type NavItem = { href: string; label: string }

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

const pageNav: Record<Audience, NavItem[]> = {
  overview: [
    { href: "#model", label: "Mental model" },
    { href: "#paths", label: "Choose a guide" },
    { href: "#channels", label: "Channels" },
    { href: "#scoring", label: "Scoring" },
    { href: "#safety", label: "Safety boundary" },
  ],
  developers: [
    { href: "#start", label: "Install" },
    { href: "#trace", label: "Trace model" },
    { href: "#sdk", label: "Python SDK" },
    { href: "#integrations", label: "Integrations" },
    { href: "#ci", label: "CI gate" },
    { href: "#api", label: "Cloud API" },
  ],
  agents: [
    { href: "#start", label: "Start" },
    { href: "#rules", label: "Operating rules" },
    { href: "#loop", label: "Improvement loop" },
    { href: "#errors", label: "Failure handling" },
    { href: "#binding", label: "REST binding" },
    { href: "#completion", label: "Completion report" },
  ],
}

function DocWordmark() {
  return (
    <Link to="/" className="docs-wordmark" aria-label="AgentLeak home">
      <span>AgentLeak</span>
      <em>Docs</em>
    </Link>
  )
}

function Code({ children }: { children: string }) {
  return (
    <pre className="docs-code">
      <code>{children}</code>
    </pre>
  )
}

function DocHeader({ audience }: { audience: Audience }) {
  return (
    <header className="docs-header">
      <DocWordmark />
      <nav aria-label="Documentation">
        <Link className={audience === "overview" ? "active" : ""} to="/docs">
          Overview
        </Link>
        <Link className={audience === "developers" ? "active" : ""} to="/docs/developers">
          Developers
        </Link>
        <Link className={audience === "agents" ? "active" : ""} to="/docs/agents">
          Agents
        </Link>
      </nav>
      <div className="docs-header-actions">
        <a href="/api/docs">API reference</a>
        <Link to="/register">Get started</Link>
      </div>
    </header>
  )
}

function DocSidebar({ audience }: { audience: Audience }) {
  return (
    <aside className="docs-sidebar" aria-label="Documentation sidebar">
      <div className="docs-sidebar-group">
        <p>Guides</p>
        <Link className={audience === "overview" ? "active" : ""} to="/docs">
          Overview
        </Link>
        <Link className={audience === "developers" ? "active" : ""} to="/docs/developers">
          Developers
        </Link>
        <Link className={audience === "agents" ? "active" : ""} to="/docs/agents">
          Agents
        </Link>
      </div>
      <div className="docs-sidebar-group">
        <p>Reference</p>
        <a href="/api/docs">Interactive API</a>
        <a href="/openapi.json">OpenAPI schema</a>
        <a href="/.well-known/agent-card.json">Agent Card</a>
      </div>
      <div className="docs-sidebar-group">
        <p>Machine readable</p>
        <a href="/llms.txt">llms.txt</a>
        <a href="/llms-full.txt">llms-full.txt</a>
        <a href="/agents.md">agents.md</a>
      </div>
    </aside>
  )
}

function PageToc({ audience }: { audience: Audience }) {
  return (
    <aside className="docs-toc" aria-label="On this page">
      <p>On this page</p>
      {pageNav[audience].map((item) => (
        <a key={item.href} href={item.href}>
          {item.label}
        </a>
      ))}
    </aside>
  )
}

function Overview() {
  return (
    <article className="docs-article">
      <header className="docs-page-head" id="model">
        <p className="docs-kicker">Documentation</p>
        <h1>AgentLeak documentation</h1>
        <p>
          AgentLeak is a privacy test harness for agent systems. It follows sensitive data through
          internal execution channels, shows where it escaped, and turns the result into a policy
          decision that a team can audit.
        </p>
      </header>

      <section className="docs-section">
        <h2>Mental model</h2>
        <p>
          A trace is an ordered record of what an agent received, called, shared, wrote and returned.
          AgentLeak detects sensitive values, builds the exposed inventory, then measures which values
          crossed an unauthorized boundary.
        </p>
        <div className="docs-flow" aria-label="AgentLeak analysis flow">
          <span>Trace</span>
          <span>Detect</span>
          <span>Follow</span>
          <span>Score</span>
          <span>Gate</span>
        </div>
      </section>

      <section className="docs-section" id="paths">
        <h2>Choose a guide</h2>
        <div className="docs-card-grid">
          <Link to="/docs/developers">
            <h3>Developer guide</h3>
            <p>Install the SDK, capture traces, run locally, and fail CI on privacy regression.</p>
          </Link>
          <Link to="/docs/agents">
            <h3>Agent instructions</h3>
            <p>Discover the service, onboard safely, scan authorized code, and report results.</p>
          </Link>
        </div>
      </section>

      <section className="docs-section" id="channels">
        <h2>Channels</h2>
        <p>AgentLeak treats the complete run as the privacy boundary, not only the final answer.</p>
        <div className="docs-token-grid">
          {[
            "user_input",
            "tool_call",
            "tool_response",
            "inter_agent_message",
            "shared_memory",
            "log",
            "generated_file",
            "final_output",
          ].map((channel) => (
            <code key={channel}>{channel}</code>
          ))}
        </div>
      </section>

      <section className="docs-section" id="scoring">
        <h2>Scoring</h2>
        <dl className="docs-definition">
          <div>
            <dt>Risk Index</dt>
            <dd>0 to 1. Higher means more severity-weighted sensitive inventory escaped.</dd>
          </div>
          <div>
            <dt>Privacy score</dt>
            <dd>100 to 0. Human-readable inverse presentation of the same risk.</dd>
          </div>
          <div>
            <dt>Finding level</dt>
            <dd>L4 to L1. Critical, high, medium and low severity.</dd>
          </div>
        </dl>
      </section>

      <section className="docs-section" id="safety">
        <h2>Safety boundary</h2>
        <p>
          A passing run proves that the tested trace met the configured policy. It does not prove that
          every future run is safe, replace legal review, or authorize an agent to upload production
          data. Use synthetic or canary values by default.
        </p>
      </section>
    </article>
  )
}

function Developers() {
  return (
    <article className="docs-article">
      <header className="docs-page-head" id="start">
        <p className="docs-kicker">Developer guide</p>
        <h1>Instrument once. Test every run.</h1>
        <p>
          Use AgentLeak from the CLI, Python SDK, framework adapters, or hosted HTTP API. The core
          analyzer runs locally with no required network calls.
        </p>
      </header>

      <section className="docs-section">
        <h2>Install</h2>
        <Code>{INSTALL}</Code>
      </section>

      <section className="docs-section" id="trace">
        <h2>Trace model</h2>
        <p>
          Record events at system boundaries. Each event identifies a channel, source, target and
          content. Preserve ordering and use stable names so leak paths stay comparable across runs.
        </p>
        <Code>{TRACE}</Code>
      </section>

      <section className="docs-section" id="sdk">
        <h2>Python SDK</h2>
        <Code>{SDK}</Code>
      </section>

      <section className="docs-section" id="integrations">
        <h2>Integrations</h2>
        <p>
          The unified <code>agentleak.watch()</code> recorder supports direct channel calls and
          adapters for the major agent runtimes.
        </p>
        <div className="docs-token-grid">
          {[
            "LangChain / LangGraph",
            "CrewAI",
            "AutoGen",
            "OpenAI Agents",
            "LlamaIndex",
            "Semantic Kernel",
            "Pydantic AI",
            "smolagents",
            "Google ADK",
            "OpenTelemetry",
            "MCP",
          ].map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
        <p>
          <a href="https://github.com/yagobski/agentleak-oss/blob/main/docs/integrations.md">
            View adapter examples
          </a>
        </p>
      </section>

      <section className="docs-section" id="ci">
        <h2>CI gate</h2>
        <Code>{CI}</Code>
        <p>
          Keep test traces synthetic and versioned. Compare privacy score, Risk Index, channel
          findings and leak paths between releases.
        </p>
      </section>

      <section className="docs-section" id="api">
        <h2>Cloud API</h2>
        <p>
          The hosted service exposes OpenAPI, interactive Swagger documentation, project-scoped keys
          and a free BYOK-compatible tier.
        </p>
        <div className="docs-link-list">
          <a href="/openapi.json">
            <code>GET /openapi.json</code>
            <span>OpenAPI schema</span>
          </a>
          <a href="/api/docs">
            <code>GET /api/docs</code>
            <span>Interactive API reference</span>
          </a>
          <a href="/api/meta">
            <code>GET /api/meta</code>
            <span>Runtime capabilities</span>
          </a>
        </div>
      </section>
    </article>
  )
}

function Agents() {
  return (
    <article className="docs-article">
      <header className="docs-page-head" id="start">
        <p className="docs-kicker">Agent instructions</p>
        <h1>If you are an agent, start here.</h1>
        <p>
          You can discover AgentLeak, create a project, analyze authorized source and runtime
          behavior, apply prioritized fixes, and verify the result without using a browser.
        </p>
        <div className="docs-callout">
          <strong>Discovery</strong>
          <code>GET {BASE}/llms.txt</code>
          <code>GET {BASE}/openapi.json</code>
        </div>
      </header>

      <section className="docs-section" id="rules">
        <h2>Operating rules</h2>
        <ol className="docs-rules">
          <li>
            <strong>MUST</strong>
            <span>Have owner authorization before sending source code or traces.</span>
          </li>
          <li>
            <strong>SHOULD</strong>
            <span>Use synthetic, masked or canary values.</span>
          </li>
          <li>
            <strong>MUST NOT</strong>
            <span>Send production credentials or real personal data without explicit authorization.</span>
          </li>
          <li>
            <strong>MUST</strong>
            <span>Keep the project key out of prompts, logs, URLs, source control and trace content.</span>
          </li>
          <li>
            <strong>MUST NOT</strong>
            <span>Treat a passing trace as universal safety or legal certification.</span>
          </li>
        </ol>
        <p>
          <a href="/agents.md">Read normative agent instructions</a>
        </p>
      </section>

      <section className="docs-section" id="loop">
        <h2>Improvement loop</h2>
        <div className="docs-steps">
          {[
            ["1", "Onboard", "Create the account, project and scoped API key."],
            ["2", "Register", "Declare identity, capabilities, data types and optional source."],
            ["3", "Test", "Scan authorized code and submit a synthetic runtime trace."],
            ["4", "Improve", "Apply the highest-priority safe next_step."],
            ["5", "Verify", "Run again, inspect delta, report unresolved risk."],
          ].map(([step, title, body]) => (
            <div key={step}>
              <b>{step}</b>
              <h3>{title}</h3>
              <p>{body}</p>
            </div>
          ))}
        </div>
        <Code>{ONBOARD}</Code>
        <p>
          Store the returned <code>api_key</code> securely. Send it as <code>X-AgentLeak-Key</code>{" "}
          on every later agent request.
        </p>
      </section>

      <section className="docs-section" id="errors">
        <h2>Failure handling</h2>
        <div className="docs-table">
          {[
            ["401", "Stop. Request a valid project key. Never guess credentials."],
            ["409", "The account exists. Do not create variants to bypass ownership."],
            ["422", "Repair the payload against OpenAPI, then retry once."],
            ["429", "Honor X-Quota-Reset and back off. Never evade limits."],
            ["5xx", "Use bounded exponential backoff and preserve idempotency."],
          ].map(([code, description]) => (
            <div key={code}>
              <code>{code}</code>
              <span>{description}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="docs-section" id="binding">
        <h2>AgentLeak REST binding</h2>
        <p id="agentleak-rest-binding">
          The well-known Agent Card declares a custom HTTP+JSON binding identified by this section.
          AgentLeak does not expose the standard A2A message/task transport. Use OpenAPI for request
          and response schemas.
        </p>
        <div className="docs-link-list">
          <a href="/.well-known/agent-card.json">
            <code>GET /.well-known/agent-card.json</code>
            <span>Capabilities</span>
          </a>
          <a href="/agents.md">
            <code>GET /agents.md</code>
            <span>Instructions</span>
          </a>
          <a href="/llms-full.txt">
            <code>GET /llms-full.txt</code>
            <span>Full context</span>
          </a>
        </div>
      </section>

      <section className="docs-section" id="completion">
        <h2>Completion report</h2>
        <p>
          Return the project ID, run ID, privacy score, Risk Index, pass/fail status, delta,
          remaining findings by severity, code-scan status and actions that still require human
          approval. Never include raw secrets.
        </p>
      </section>
    </article>
  )
}

export function Documentation({ audience = "overview" }: { audience?: Audience }) {
  return (
    <div className="docs-shell">
      <DocHeader audience={audience} />
      <div className="docs-layout">
        <DocSidebar audience={audience} />
        <main>{audience === "developers" ? <Developers /> : audience === "agents" ? <Agents /> : <Overview />}</main>
        <PageToc audience={audience} />
      </div>
      <footer className="docs-footer">
        <DocWordmark />
        <p>Documentation for people and agents.</p>
        <Link to="/">Back to AgentLeak</Link>
      </footer>
    </div>
  )
}
