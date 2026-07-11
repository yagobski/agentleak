import { Link } from "react-router-dom"

type Audience = "overview" | "developers" | "agents" | "api"
type NavItem = { href: string; label: string }
type Endpoint = {
  method: "GET" | "POST" | "PATCH" | "PUT" | "DELETE"
  path: string
  auth: "None" | "Session cookie" | "X-AgentLeak-Key" | "Session or project key"
  summary: string
  request: string
  response: string
}

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
  '    {"channel":"user_input","source":"user","target":"agent",',
  '     "content":"Book a follow-up for Maya Tremblay."},',
  '    {"channel":"tool_response","source":"crm","target":"agent",',
  '     "content":{"email":"canary@example.test","sin":"123-456-789"}},',
  '    {"channel":"tool_call","source":"agent","target":"calendar",',
  '     "content":{"email":"canary@example.test"}},',
  '    {"channel":"final_output","source":"agent","target":"user",',
  '     "content":"Follow-up scheduled."}',
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
  "print(result.risk_index, result.privacy_score, result.verdict)",
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
const SELFTEST = [
  "curl -sS -X POST " + BASE + "/api/selftest \\",
  "  -H \"X-AgentLeak-Key: $AGENTLEAK_KEY\" \\",
  "  -H 'content-type: application/json' \\",
  "  -d '{",
  "    \"trace\": {\"run_id\":\"run_001\",\"events\":[...]},",
  "    \"detectors\": {\"pii\": true, \"secrets\": true},",
  "    \"redact\": true",
  "  }'",
].join("\n")
const AGENT_REGISTER = [
  "curl -sS -X POST " + BASE + "/api/agent/register \\",
  "  -H \"X-AgentLeak-Key: $AGENTLEAK_KEY\" \\",
  "  -H 'content-type: application/json' \\",
  "  -d '{",
  "    \"agent_card\": {",
  "      \"name\": \"support-bot\",",
  "      \"capabilities\": [\"ticket_triage\", \"crm_lookup\"],",
  "      \"privacy\": {\"declared_data_types\": [\"email\", \"phone_number\"]},",
  "      \"source\": {\"type\": \"github\", \"repo\": \"acme/support-bot\"}",
  "    }",
  "  }'",
].join("\n")
const OPENAPI_FETCH = [
  "curl -sS " + BASE + "/openapi.json | jq '.paths | keys'",
  "",
  "# Swagger remains available when you need raw schema exploration:",
  "open " + BASE + "/api/docs",
].join("\n")
const RISK_FORMULA = [
  "WSL(t) = sum(weight(level(secret))) for distinct leaked secrets",
  "rho_S  = sum(weight(level(secret))) for the audited sensitive vault",
  "RI(t)  = WSL(t) / rho_S",
  "",
  "privacy_score = round(100 * (1 - RI))",
].join("\n")

const pageNav: Record<Audience, NavItem[]> = {
  overview: [
    { href: "#model", label: "Mental model" },
    { href: "#how-to-use", label: "How to use AgentLeak" },
    { href: "#agentrisk", label: "AgentRisk" },
    { href: "#channels", label: "Channels" },
    { href: "#safety", label: "Safety boundary" },
  ],
  developers: [
    { href: "#start", label: "Install" },
    { href: "#workflow", label: "Developer workflow" },
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
    { href: "#register", label: "Register identity" },
    { href: "#errors", label: "Failure handling" },
    { href: "#binding", label: "REST binding" },
    { href: "#completion", label: "Completion report" },
  ],
  api: [
    { href: "#auth", label: "Authentication" },
    { href: "#quick-calls", label: "Quick calls" },
    { href: "#endpoints", label: "Endpoint reference" },
    { href: "#schemas", label: "Core schemas" },
    { href: "#errors", label: "Errors" },
    { href: "#openapi", label: "OpenAPI" },
  ],
}

const apiEndpoints: Endpoint[] = [
  {
    method: "GET",
    path: "/api/meta",
    auth: "None",
    summary: "Discover runtime version, supported channels, detectors, framework labels, docs links and free-tier limits.",
    request: "No body.",
    response: "version, channels, detectors, agent_api, documentation, free_tier.",
  },
  {
    method: "POST",
    path: "/api/auth/register",
    auth: "None",
    summary: "Create a human account and session cookie for the hosted platform.",
    request: "email, password, optional name.",
    response: "Authenticated user object. The server sets the session cookie.",
  },
  {
    method: "POST",
    path: "/api/projects",
    auth: "Session cookie",
    summary: "Create a project for one agent, one multi-agent workflow, or one product surface.",
    request: "name, optional agent_type, description and config.",
    response: "Project with id, config, run counts and timestamps.",
  },
  {
    method: "POST",
    path: "/api/analyze",
    auth: "Session cookie",
    summary: "Analyze a raw trace without attaching it to a saved project run.",
    request: "trace or scenario_id, detector toggles, custom detectors, vault settings and redact flag.",
    response: "AgentRisk report with risk_index, privacy_score, findings, channel_risks and recommendations.",
  },
  {
    method: "POST",
    path: "/api/projects/{project_id}/api-key",
    auth: "Session cookie",
    summary: "Generate a project-scoped key for autonomous agent calls.",
    request: "No body.",
    response: "api_key and project_id. Store the key once; treat it like a secret.",
  },
  {
    method: "POST",
    path: "/api/selftest",
    auth: "X-AgentLeak-Key",
    summary: "Submit one runtime trace from an agent and receive a pass/fail self-test result.",
    request: "trace, detectors, custom_detectors, vault and redact.",
    response: "report, passed, compliant, project_id and run_id.",
  },
  {
    method: "POST",
    path: "/api/agent/onboard",
    auth: "None",
    summary: "Agent-friendly onboarding that creates an account, project and project key in one call.",
    request: "email plus optional agent_name.",
    response: "project_id, api_key, instructions and next links.",
  },
  {
    method: "POST",
    path: "/api/agent/register",
    auth: "X-AgentLeak-Key",
    summary: "Upsert the agent card: identity, capabilities, declared data types and optional source location.",
    request: "agent_card object.",
    response: "project_id and normalized agent_card.",
  },
  {
    method: "POST",
    path: "/api/agent/code",
    auth: "X-AgentLeak-Key",
    summary: "Scan declared or submitted source code before runtime execution.",
    request: "Empty body for declared source, or source=github|zip|files with source details.",
    response: "scan id, verdict, score, findings, tier/confidence and redacted snippets.",
  },
  {
    method: "POST",
    path: "/api/agent/improve",
    auth: "X-AgentLeak-Key",
    summary: "Run a self-test, compare with previous runs and return machine-actionable next_steps.",
    request: "trace plus optional detector/vault settings.",
    response: "report, passed, delta, progression, code_scan summary and prioritized next_steps.",
  },
  {
    method: "GET",
    path: "/api/agent/status",
    auth: "X-AgentLeak-Key",
    summary: "Read latest score, compliance posture, code scan state, progression and remaining work.",
    request: "No body.",
    response: "project, latest_run, progression, compliance, code_scan and next_steps.",
  },
  {
    method: "GET",
    path: "/openapi.json",
    auth: "None",
    summary: "Machine-readable OpenAPI schema for generated clients, validators and agent planning.",
    request: "No body.",
    response: "OpenAPI 3 schema.",
  },
]

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
        <Link className={audience === "api" ? "active" : ""} to="/docs/api">
          API
        </Link>
      </nav>
      <div className="docs-header-actions">
        <Link to="/docs/api">API reference</Link>
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
        <Link className={audience === "api" ? "active" : ""} to="/docs/api">
          API reference
        </Link>
        <a href="/openapi.json">OpenAPI schema</a>
        <a href="/api/docs">Swagger UI</a>
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
          AgentLeak tests whether agents leak sensitive data across the whole execution path:
          prompts, tools, memory, inter-agent messages, generated files, logs and final outputs.
          It returns evidence, a deterministic AgentRisk score and remediation steps that both
          humans and autonomous agents can act on.
        </p>
      </header>

      <section className="docs-section">
        <h2>Mental model</h2>
        <p>
          A trace is an ordered record of what an agent received, called, shared, wrote and returned.
          AgentLeak detects sensitive values, builds the exposed inventory, follows where those
          values moved, then decides whether the run crossed a privacy boundary.
        </p>
        <div className="docs-flow" aria-label="AgentLeak analysis flow">
          <span>Trace</span>
          <span>Detect</span>
          <span>Follow</span>
          <span>Score</span>
          <span>Remediate</span>
          <span>Gate</span>
        </div>
      </section>

      <section className="docs-section" id="how-to-use">
        <h2>How to use AgentLeak</h2>
        <div className="docs-steps">
          {[
            ["1", "Choose a boundary", "Decide what system is under audit: one agent, a workflow, a tool chain or a multi-agent handoff."],
            ["2", "Capture a trace", "Record events at trust boundaries: user input, tool calls, tool responses, memory, logs and outputs."],
            ["3", "Define the vault", "Use observed sensitive data by default, or provide an explicit vault manifest for stricter policy scoring."],
            ["4", "Run analysis", "Use the CLI, SDK, web UI or API. Keep synthetic or canary data in tests whenever possible."],
            ["5", "Fix and gate", "Follow prioritized findings, re-run the trace, then fail CI or deployment when the threshold is crossed."],
          ].map(([step, title, body]) => (
            <div key={step}>
              <b>{step}</b>
              <h3>{title}</h3>
              <p>{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="docs-section" id="agentrisk">
        <h2>AgentLeak and AgentRisk</h2>
        <p>
          AgentLeak is the testing system. AgentRisk is the scoring layer inside it. AgentLeak finds
          sensitive data, leak paths and affected channels; AgentRisk converts those findings into a
          severity-weighted Risk Index from 0 to 1.
        </p>
        <Code>{RISK_FORMULA}</Code>
        <dl className="docs-definition">
          <div>
            <dt>0.00 RI</dt>
            <dd>No sensitive value crossed an unauthorized disclosure channel in the tested trace.</dd>
          </div>
          <div>
            <dt>0.44 RI</dt>
            <dd>44 percent of the audited sensitive inventory leaked after severity weighting.</dd>
          </div>
          <div>
            <dt>1.00 RI</dt>
            <dd>The whole audited vault leaked. This is a complete boundary failure.</dd>
          </div>
        </dl>
      </section>

      <section className="docs-section" id="channels">
        <h2>Channels</h2>
        <p>
          AgentLeak treats the complete run as the privacy boundary. A final answer can be clean
          while a tool argument, shared memory entry or inter-agent message leaked the value earlier.
        </p>
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

      <section className="docs-section" id="safety">
        <h2>Safety boundary</h2>
        <p>
          A passing run proves that the tested trace met the configured policy. It does not prove that
          every future run is safe, replace legal review, or authorize an agent to upload production
          data. Use synthetic, masked or canary values by default.
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
          Use AgentLeak from the CLI, Python SDK, framework adapters, hosted API or local web UI.
          The core analyzer runs locally, so teams can test traces before sending anything to a
          hosted service.
        </p>
      </header>

      <section className="docs-section">
        <h2>Install</h2>
        <Code>{INSTALL}</Code>
        <p>
          Use <code>agentleak[gui]</code> when you want the local browser interface. Use the core
          package for CI, SDK integration or offline trace analysis.
        </p>
      </section>

      <section className="docs-section" id="workflow">
        <h2>Developer workflow</h2>
        <div className="docs-card-grid">
          <div>
            <h3>Local regression tests</h3>
            <p>Commit synthetic traces under version control and run them in CI with a score gate.</p>
          </div>
          <div>
            <h3>Pre-production audits</h3>
            <p>Capture traces from staging agents and compare AgentRisk deltas before release.</p>
          </div>
          <div>
            <h3>Code and trace coverage</h3>
            <p>Scan source for hardcoded secrets, then analyze runtime traces for actual movement.</p>
          </div>
          <div>
            <h3>Multi-agent boundaries</h3>
            <p>Mark inter-agent messages explicitly so handoffs are scored as first-class channels.</p>
          </div>
        </div>
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
          adapters for major agent runtimes. When an adapter is not available, emit the trace schema
          directly; AgentLeak does not require a specific orchestration framework.
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
          findings and leak paths between releases. A regression should fail the build before a
          leak-prone prompt, tool mapping or memory policy ships.
        </p>
      </section>

      <section className="docs-section" id="api">
        <h2>Cloud API</h2>
        <p>
          The hosted service exposes a project dashboard, agent-side endpoints and an integrated API
          reference. Use the docs page first; use OpenAPI or Swagger when generating clients or
          validating exact schemas.
        </p>
        <div className="docs-link-list">
          <Link to="/docs/api">
            <code>GET /docs/api</code>
            <span>Integrated API guide</span>
          </Link>
          <a href="/openapi.json">
            <code>GET /openapi.json</code>
            <span>OpenAPI schema</span>
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
          <code>GET {BASE}/agents.md</code>
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
            <strong>MUST</strong>
            <span>Follow highest-priority next_steps first, unless they require human approval.</span>
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
            ["3", "Scan", "Scan authorized source code before runtime testing."],
            ["4", "Test", "Submit a synthetic or authorized runtime trace."],
            ["5", "Improve", "Apply highest-priority safe next_steps."],
            ["6", "Verify", "Run again, inspect delta, report unresolved risk."],
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

      <section className="docs-section" id="register">
        <h2>Register identity and source</h2>
        <p>
          Register an agent card before scanning or improving. Include the agent name, capabilities,
          declared data types and optional source location. AgentLeak accepts simple cards and
          well-known Agent Card shapes used by A2A-style ecosystems.
        </p>
        <Code>{AGENT_REGISTER}</Code>
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
          and response schemas, and use this page for the intended operating flow.
        </p>
        <div className="docs-link-list">
          <a href="/.well-known/agent-card.json">
            <code>GET /.well-known/agent-card.json</code>
            <span>Capabilities</span>
          </a>
          <Link to="/docs/api">
            <code>GET /docs/api</code>
            <span>API guide</span>
          </Link>
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

function ApiReference() {
  return (
    <article className="docs-article">
      <header className="docs-page-head">
        <p className="docs-kicker">API reference</p>
        <h1>AgentLeak API</h1>
        <p>
          This reference is built into the documentation so developers and agents can understand the
          API flow without leaving the docs. Swagger is still available for schema exploration, but
          the recommended path is this guide plus the OpenAPI schema for exact types.
        </p>
      </header>

      <section className="docs-section" id="auth">
        <h2>Authentication</h2>
        <div className="docs-card-grid">
          <div>
            <h3>Human platform calls</h3>
            <p>
              Register or log in through <code>/api/auth/*</code>. The server sets a session cookie
              used by project, run, scenario and dashboard endpoints.
            </p>
          </div>
          <div>
            <h3>Agent-side calls</h3>
            <p>
              Generate or receive an <code>ak_...</code> project key and send it as{" "}
              <code>X-AgentLeak-Key</code>. Never place it in URLs, prompts, traces or source code.
            </p>
          </div>
        </div>
      </section>

      <section className="docs-section" id="quick-calls">
        <h2>Quick calls</h2>
        <p>Use these as the shortest working path for an autonomous agent integration.</p>
        <Code>{ONBOARD}</Code>
        <Code>{SELFTEST}</Code>
      </section>

      <section className="docs-section" id="endpoints">
        <h2>Endpoint reference</h2>
        <div className="docs-api-list">
          {apiEndpoints.map((endpoint) => (
            <article key={`${endpoint.method}-${endpoint.path}`} className="docs-api-endpoint">
              <div className="docs-api-title">
                <span data-method={endpoint.method}>{endpoint.method}</span>
                <code>{endpoint.path}</code>
              </div>
              <p>{endpoint.summary}</p>
              <dl>
                <div>
                  <dt>Auth</dt>
                  <dd>{endpoint.auth}</dd>
                </div>
                <div>
                  <dt>Request</dt>
                  <dd>{endpoint.request}</dd>
                </div>
                <div>
                  <dt>Returns</dt>
                  <dd>{endpoint.response}</dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      </section>

      <section className="docs-section" id="schemas">
        <h2>Core schemas</h2>
        <div className="docs-table">
          {[
            ["Trace", "run_id, agent_name and ordered events with channel, source, target and content."],
            ["Finding", "channel, data_type, severity, level_label, confidence, redacted_value and recommendation."],
            ["Report", "risk_index, privacy_score, verdict, channel_risks, findings, remediation_hints and compliance."],
            ["Agent card", "name, capabilities, protocol metadata, declared data types and optional source location."],
            ["Next step", "kind, priority, action, channel or framework context, and optional code_fix."],
          ].map(([name, description]) => (
            <div key={name}>
              <code>{name}</code>
              <span>{description}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="docs-section" id="errors">
        <h2>Errors and retries</h2>
        <p>
          Treat 401 as a hard auth failure, 409 as ownership/account conflict, 422 as schema repair,
          429 as a backoff signal and 5xx as a bounded retry. Agents should preserve idempotency and
          include no raw secrets in final reports.
        </p>
      </section>

      <section className="docs-section" id="openapi">
        <h2>OpenAPI and Swagger</h2>
        <p>
          Use OpenAPI as the authoritative contract for field names and generated clients. Use the
          built-in Swagger UI only when you need raw schema exploration.
        </p>
        <Code>{OPENAPI_FETCH}</Code>
      </section>
    </article>
  )
}

function renderAudience(audience: Audience) {
  if (audience === "developers") return <Developers />
  if (audience === "agents") return <Agents />
  if (audience === "api") return <ApiReference />
  return <Overview />
}

export function Documentation({ audience = "overview" }: { audience?: Audience }) {
  return (
    <div className="docs-shell">
      <DocHeader audience={audience} />
      <div className="docs-layout">
        <DocSidebar audience={audience} />
        <main>{renderAudience(audience)}</main>
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
