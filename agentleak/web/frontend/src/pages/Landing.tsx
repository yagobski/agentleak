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
import { BrandLogo, ECOSYSTEM_LOGOS } from "@/features/BrandLogos"
import { AgentLeakLogo } from "@/features/AgentLeakLogo"
import {
  AgentTerminal,
  Arrow,
  CIGateDemo,
  OpenSourceDemo,
  PlatformWorkbench,
  RunReportDemo,
  usePrefersReducedMotion,
} from "@/features/ProductDemos"
import {
  FEATURE_PAGES,
  FAQ_ITEMS,
  FaqItem,
  REPO_URL,
  SITE_URL,
  SiteFooter,
  SiteNav,
  usePageMeta,
} from "@/features/SiteChrome"

const HERO_RUNS = [
  ["support-router", "agent:selftest", "now", "0.38", "Fail", "2 leaked", true],
  ["claims-reviewer", "ci · release-42", "8m", "0.12", "Pass", "clean", false],
  ["patient-summary", "ci · nightly", "21m", "0.64", "Blocked", "4 leaked", true],
  ["finance-copilot", "playground", "1h", "0.08", "Pass", "clean", false],
  ["onboarding-bot", "agent:improve", "2h", "0.22", "Conditional", "1 leaked", true],
] as const

// Interactive hero: a faithful miniature of the real Dashboard whose views the
// visitor can switch, echoing cursor.com/cloud where the preview is navigable.
const HERO_VIEWS = ["Dashboard", "Runs", "Playground", "Leaderboard", "Scenarios"] as const

function HeroPlatform() {
  const [view, setView] = useState<(typeof HERO_VIEWS)[number]>("Dashboard")
  const [activeRun, setActiveRun] = useState(0)
  const reducedMotion = usePrefersReducedMotion()

  useEffect(() => {
    if (reducedMotion || view !== "Dashboard") return
    const timer = window.setInterval(() => setActiveRun((current) => (current + 1) % HERO_RUNS.length), 2100)
    return () => window.clearInterval(timer)
  }, [reducedMotion, view])

  return (
    <div className="cursor-demo cursor-app" aria-label="The AgentLeak dashboard with a full workspace of scored agents">
      <div className="cursor-demo-bar">
        <div><span /><span /><span /></div>
        <p>AgentLeak / {view}</p>
        <b>100% local · v0.8.0</b>
      </div>
      <div className="cursor-app-body">
        <aside className="cursor-app-side">
          <div className="cursor-app-brand"><AgentLeakLogo className="agentleak-logo-preview" label="" /></div>
          <small>Platform</small>
          <button type="button" data-active={view === "Dashboard"} onClick={() => setView("Dashboard")}><LayoutDashboard /> Dashboard</button>
          <button type="button" data-active={view === "Runs"} onClick={() => setView("Runs")}><FolderKanban /> Runs</button>
          <button type="button" data-active={view === "Playground"} onClick={() => setView("Playground")}><FlaskConical /> Playground</button>
          <button type="button" data-active={view === "Leaderboard"} onClick={() => setView("Leaderboard")}><Trophy /> Leaderboard</button>
          <button type="button" data-active={view === "Scenarios"} onClick={() => setView("Scenarios")}><Library /> Scenarios</button>
          <div className="cursor-app-side-foot">
            <button type="button"><Settings /> Settings</button>
            <em>acme-ops</em>
          </div>
        </aside>
        <section className="cursor-app-main">
          {view === "Dashboard" && (
            <>
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
              <div className="cursor-app-chart" aria-label="AgentRisk trend over the last 30 runs">
                <header><span>AgentRisk trend</span><small>30 runs · lower is safer</small></header>
                <svg viewBox="0 0 800 90" preserveAspectRatio="none" aria-hidden="true">
                  <path className="cursor-app-chart-fill" d="M0 72 L55 68 L110 74 L165 59 L220 63 L275 50 L330 56 L385 44 L440 48 L495 35 L550 40 L605 28 L660 32 L715 21 L800 12 L800 90 L0 90 Z" />
                  <path className="cursor-app-chart-line" d="M0 72 L55 68 L110 74 L165 59 L220 63 L275 50 L330 56 L385 44 L440 48 L495 35 L550 40 L605 28 L660 32 L715 21 L800 12" />
                </svg>
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
            </>
          )}
          {view === "Runs" && (
            <>
              <header className="cursor-app-head">
                <div><h4>Runs</h4><p>Every analysis, newest first. Click one to open its report.</p></div>
                <b>New run</b>
              </header>
              <div className="cursor-app-runs cursor-app-runs-full">
                <header><span>All runs</span><code>128 total</code></header>
                {HERO_RUNS.map(([agent, source, when, ri, verdict, leaks, hot]) => (
                  <article key={agent} data-hot={hot}>
                    <b>{agent}</b>
                    <small>{source}</small>
                    <span>{leaks} · RI {ri}</span>
                    <em data-verdict={verdict}>{verdict}</em>
                    <code>{when}</code>
                  </article>
                ))}
              </div>
            </>
          )}
          {view === "Playground" && (
            <>
              <header className="cursor-app-head">
                <div><h4>Playground</h4><p>Paste a trace and inspect the privacy decision instantly.</p></div>
                <b>Run audit</b>
              </header>
              <div className="cursor-app-playground">
                <section>
                  <header><span>Execution trace</span><code>support-router.json</code></header>
                  <pre>{`{
  "agent_name": "support-router",
  "events": [
    {"channel": "tool_response", "content": "[private customer record]"},
    {"channel": "shared_memory", "content": "account_id: acct_••••7F2"},
    {"channel": "final_output", "content": "Your request is complete."}
  ]
}`}</pre>
                </section>
                <aside>
                  <small>PRIVACY SCORE</small>
                  <strong>62</strong><span>/ 100</span>
                  <i><b /></i>
                  <dl>
                    <div><dt>Risk Index</dt><dd>0.38</dd></div>
                    <div><dt>Leak paths</dt><dd>2</dd></div>
                    <div><dt>Decision</dt><dd data-hot="true">Review</dd></div>
                  </dl>
                  <p>Redact <code>account_id</code> before shared memory.</p>
                </aside>
              </div>
            </>
          )}
          {view === "Leaderboard" && (
            <>
              <header className="cursor-app-head">
                <div><h4>Agent leaderboard</h4><p>Latest AgentRisk result per agent. Lower risk wins.</p></div>
                <b>This month</b>
              </header>
              <div className="cursor-app-board">
                {[["finance-copilot", "92", "0.08"], ["claims-reviewer", "88", "0.12"], ["onboarding-bot", "78", "0.22"], ["support-router", "62", "0.38"], ["patient-summary", "36", "0.64"]].map(([name, score, ri], index) => (
                  <div className="cursor-app-board-row" key={name} data-top={index === 0}>
                    <i>{index + 1}</i>
                    <b>{name}</b>
                    <div className="cursor-app-board-bar"><span style={{ width: `${score}%` }} /></div>
                    <code>{score}</code>
                    <em>RI {ri}</em>
                  </div>
                ))}
              </div>
            </>
          )}
          {view === "Scenarios" && (
            <>
              <header className="cursor-app-head">
                <div><h4>Scenario library</h4><p>Realistic leak probes and clean controls across sensitive domains.</p></div>
                <b>Import pack</b>
              </header>
              <div className="cursor-app-scenarios">
                <header><span>Scenario</span><span>Domain</span><span>Behavior</span><span>Coverage</span></header>
                {[
                  ["Patient summary handoff", "Healthcare", "Leak probe", "PHI · memory · messages"],
                  ["Loan review assistant", "Finance", "Leak probe", "Account · tools · logs"],
                  ["Employee onboarding", "HR", "Clean control", "SIN · files · output"],
                  ["Student support routing", "Education", "Clean control", "ID · tools · output"],
                  ["CRM escalation", "Support", "Leak probe", "Email · memory · tools"],
                ].map(([name, domain, behavior, coverage]) => (
                  <article key={name} data-clean={behavior === "Clean control"}>
                    <b>{name}</b>
                    <span>{domain}</span>
                    <em>{behavior}</em>
                    <small>{coverage}</small>
                  </article>
                ))}
                <footer><span>10 built in · 5 leak probes · 5 clean controls</span><b>36-scenario research pack available</b></footer>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}

const STAY_AHEAD_STEPS = ["Capture", "Detect", "Explain", "Enforce"] as const

function StayAheadSection() {
  const reducedMotion = usePrefersReducedMotion()
  const [step, setStep] = useState(reducedMotion ? 3 : 0)

  useEffect(() => {
    if (reducedMotion) {
      setStep(3)
      return
    }
    const timer = window.setInterval(() => setStep((current) => (current + 1) % STAY_AHEAD_STEPS.length), 2100)
    return () => window.clearInterval(timer)
  }, [reducedMotion])

  return (
    <section className="cursor-stay-ahead">
      <header>
        <p className="cursor-eyebrow">Stay ahead of every disclosure</p>
        <h2>Detect the leak, explain the score, stop the release.</h2>
      </header>
      <div className="cursor-stay-grid" data-step={step}>
        <article>
          <div className="cursor-stay-copy">
            <h3>See the leak inside the run</h3>
            <p>Follow sensitive values through tools, memory, messages, logs and files, even when the final answer is clean.</p>
            <Link to="/features/trace-analysis">Explore trace analysis <Arrow /></Link>
          </div>
          <div className="cursor-stay-stage cursor-stay-trace" aria-label={`Trace analysis: ${STAY_AHEAD_STEPS[step]}`}>
            <header><span>run_2048.trace</span><b>{step < 2 ? "analyzing" : "2 disclosures"}</b></header>
            {[
              ["tool_response", "customer record received", "source"],
              ["tool_call", "account_id sent to calendar", "L3"],
              ["shared_memory", "identifier persisted", "L3"],
              ["final_output", "customer answer is clean", "clean"],
            ].map(([channel, detail, level], index) => (
              <div key={channel} data-visible={step >= Math.min(index, 2)} data-hot={step >= 2 && level === "L3"}>
                <i>{index + 1}</i><span><b>{channel}</b><small>{detail}</small></span><em>{level}</em>
              </div>
            ))}
            <footer><span /><b>{step < 2 ? "following data flow" : "leak path reconstructed"}</b></footer>
          </div>
        </article>

        <article>
          <div className="cursor-stay-copy">
            <h3>Know exactly why risk changed</h3>
            <p>AgentRisk is deterministic and severity-weighted. Every point traces back to concrete evidence your team can inspect.</p>
            <Link to="/features/agentrisk">Understand AgentRisk <Arrow /></Link>
          </div>
          <div className="cursor-stay-stage cursor-stay-risk" aria-label={`AgentRisk calculation: ${STAY_AHEAD_STEPS[step]}`}>
            <header><span>AgentRisk v1</span><b>deterministic</b></header>
            <div className="cursor-stay-risk-score"><small>Privacy score</small><strong>{step < 2 ? "100" : "62"}</strong><span>/ 100</span></div>
            <div className="cursor-stay-risk-bar"><i style={{ width: step < 2 ? "100%" : "62%" }} /></div>
            <dl>
              <div data-active={step >= 2}><dt>account_id</dt><dd>L3 · shared_memory</dd></div>
              <div data-active={step >= 2}><dt>email</dt><dd>L2 · tool_call</dd></div>
            </dl>
            <footer><code>RI = WSL / rho(S)</code><span>{step < 2 ? "waiting for findings" : "RI 0.38"}</span></footer>
          </div>
        </article>

        <article>
          <div className="cursor-stay-copy">
            <h3>Turn privacy into a release gate</h3>
            <p>Run AgentLeak in any CI system. A policy crossing blocks the merge and attaches the exact remediation.</p>
            <Link to="/features/ci-gate">See the CI policy gate <Arrow /></Link>
          </div>
          <div className="cursor-stay-stage cursor-stay-ci" aria-label={`CI privacy gate: ${STAY_AHEAD_STEPS[step]}`}>
            <header><span>release-42</span><b>required checks</b></header>
            {["Build", "Unit tests", "Agent trace", "AgentLeak privacy gate"].map((label, index) => {
              const complete = step >= Math.min(index, 2)
              const failed = index === 3 && step === 3
              return <div key={label} data-complete={complete} data-failed={failed}><i>{failed ? "!" : complete ? "✓" : "·"}</i><b>{label}</b><span>{failed ? "failed" : complete ? "passed" : "waiting"}</span></div>
            })}
            <footer data-blocked={step === 3}><b>{step === 3 ? "Merge blocked" : "Checking policy"}</b><span>{step === 3 ? "Redact account_id before shared_memory" : "Privacy score must remain above 80"}</span></footer>
          </div>
        </article>
      </div>
    </section>
  )
}

export function Landing() {
  usePageMeta(
    "AgentLeak · Privacy testing for AI agents",
    "AgentLeak replays the whole agent execution trace, scores every internal channel with AgentRisk, and returns the exact fix. Open source, MIT, runs 100% local.",
    {
      structuredData: {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        name: "AgentLeak",
        applicationCategory: "DeveloperApplication",
        operatingSystem: "Linux, macOS, Windows",
        description: "Open-source privacy testing for AI agents across tool calls, memory, messages, logs, files and final output.",
        url: SITE_URL,
        downloadUrl: REPO_URL,
        license: "https://opensource.org/license/mit",
        isAccessibleForFree: true,
        codeRepository: REPO_URL,
      },
    },
  )
  return (
    <div className="cursor-site">
      <SiteNav />
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
              <Link className="cursor-button cursor-button-dark" to="/register">Create a workspace <Arrow /></Link>
              <Link className="cursor-button cursor-button-light" to="/docs/agents">Agents: discover and onboard <Arrow /></Link>
            </div>
            <p className="cursor-hero-subactions">
              Human, browser-based signup. Building an agent instead? Read the{" "}
              <Link to="/docs/agents">machine API quickstart</Link>.
            </p>
          </div>
          <HeroPlatform />
        </section>

        <section className="cursor-trust">
          <h2>Built on the agent frameworks and protocols you already use</h2>
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
              ["trace-analysis", "Trace analysis", "Replay any run across 8 normalized channels (user input, tool calls, tool responses, inter-agent messages, shared memory, logs, generated files, final output) and find every exposure."],
              ["agentrisk", "AgentRisk scoring", "A deterministic, severity-weighted risk index from 0 to 1 and a 0 to 100 privacy score. No model decides the number."],
              ["code-scan", "Static code scan", "Catch hardcoded secrets, PII in logs and sensitive values sent to third parties before the agent even runs."],
              ["red-team", "Adversarial red-team", "Replay prompt-injection and exfiltration attack classes against your agent, scripted or live."],
              ["ci-gate", "CI policy gate", "Set a boundary per project. A crossing fails the job, and a required job blocks the merge."],
              ["agent-api", "Agent self-serve API", "Agents onboard in one call, test themselves and follow a bounded remediation loop, with no human in the middle."],
            ].map(([slug, title, description], index) => (
              <Link className="cursor-cap-card" to={`/features/${slug}`} key={title + index}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <h3>{title}</h3>
                <p>{description}</p>
                <b>Learn more <Arrow /></b>
              </Link>
            ))}
          </div>
        </section>

        <section className="cursor-proof-metrics" aria-label="Real numbers behind the platform">
          <header>
            <p className="cursor-eyebrow">Real numbers, not marketing</p>
            <h2>What ships in the box, and what's in the published benchmark.</h2>
          </header>
          <div className="cursor-proof-metrics-grid">
            <div><strong>8</strong><span>normalized channels every trace is scored across</span></div>
            <div><strong>10</strong><span>built-in scenarios, 5 of them clean controls with no injected leak</span></div>
            <div><strong>36</strong><span>scenarios in the published benchmark (a superset, not what ships by default)</span></div>
            <div><strong>46</strong><span>attack classes across 24 vulnerability plugins and 9 delivery strategies</span></div>
            <div><strong>7</strong><span>compliance frameworks mapped per finding, none of them a certification</span></div>
          </div>
          <p className="cursor-proof-metrics-note">
            The 10 bundled scenarios (healthcare, finance, HR, education and customer support, each with a
            leaky and a clean version) ship with the open-source tool so you can see the model work in minutes.
            The 36-scenario benchmark is the larger, separate research dataset behind the paper — see{" "}
            <Link to="/research">the research page</Link> for how the two relate.
          </p>
        </section>

        <section className="cursor-feature cursor-feature-lead" id="workflow">
          <div className="cursor-feature-copy">
            <p className="cursor-eyebrow">Complete trace analysis</p>
            <h2>The final output can be clean while the system is leaking.</h2>
            <p>Output-only checks miss what happens inside the run. AgentLeak follows sensitive values through every internal channel, reconstructs where exposure happened, assigns each finding a severity level from L1 to L4, and returns the exact remediation: prose for your team, and structured hints an agent can apply.</p>
            <Link className="cursor-textlink" to="/features/trace-analysis">Understand the trace model <Arrow /></Link>
          </div>
          <div className="cursor-feature-visual"><RunReportDemo /></div>
        </section>

        <section className="cursor-feature cursor-feature-reverse">
          <div className="cursor-feature-copy">
            <p className="cursor-eyebrow">AgentRisk</p>
            <h2>A score your team can explain.</h2>
            <p>Severity-weighted risk from 0 to 1, normalized against the audited sensitive vault. Deterministic and reproducible: the same trace always yields the same score, so a regression in CI means the agent changed, not the judge.</p>
            <Link className="cursor-textlink" to="/features/agentrisk">Learn how scoring works <Arrow /></Link>
          </div>
          <div className="cursor-feature-visual"><PlatformWorkbench /></div>
        </section>

        <section className="cursor-feature">
          <div className="cursor-feature-copy">
            <p className="cursor-eyebrow">Ship with confidence</p>
            <h2>Make privacy a required check, not a review afterthought.</h2>
            <p>Set a policy per project and wire AgentLeak into CI. When an agent crosses its boundary, the check fails and the pull request is blocked, with the offending channel and severity attached to the run.</p>
            <Link className="cursor-textlink" to="/features/ci-gate">See CI integration <Arrow /></Link>
          </div>
          <div className="cursor-feature-visual"><CIGateDemo /></div>
        </section>

        <StayAheadSection />

        <section className="cursor-feature cursor-feature-reverse">
          <div className="cursor-feature-copy">
            <p className="cursor-eyebrow">Built for autonomous agents</p>
            <h2>Agents can discover, test and improve themselves.</h2>
            <p>llms.txt discovery, one-call onboarding, scoped project keys and machine-readable remediation hints. An agent can find AgentLeak, audit itself and fix its own leaks in a bounded loop, with no browser and no human in the middle.</p>
            <Link className="cursor-textlink" to="/features/agent-api">Read agent instructions <Arrow /></Link>
          </div>
          <div className="cursor-feature-visual"><AgentTerminal /></div>
        </section>

        <section className="cursor-feature">
          <div className="cursor-feature-copy">
            <p className="cursor-eyebrow">Open source</p>
            <h2>Local-first, MIT, no telemetry.</h2>
            <p>The analyzer runs entirely on your machine. Free detection (regex, Presidio, entropy, de-obfuscation) needs no hosted model and no external detector. Run it as a CLI, self-host the platform, or use the free hosted instance for agents.</p>
            <a className="cursor-textlink" href={REPO_URL}>Star it on GitHub <Arrow /></a>
          </div>
          <div className="cursor-feature-visual"><OpenSourceDemo /></div>
        </section>

        <section className="cursor-research-band">
          <div className="cursor-research-copy">
            <p className="cursor-eyebrow">Grounded in published research</p>
            <h2>AgentLeak and AgentRisk are not marketing terms.</h2>
            <p>The framework and its scoring method come from a published benchmark of privacy leakage across agent execution traces. This tool is the open implementation of that work: the same channels, the same severity model, the same AgentRisk score.</p>
            <Link className="cursor-textlink" to="/research">See the research <Arrow /></Link>
          </div>
          <Link className="cursor-paper" to="/research">
            <div className="cursor-paper-head"><span>arXiv:2602.11510</span><em>Benchmark</em></div>
            <h4>AgentLeak: measuring privacy leakage across agent execution traces</h4>
            <div className="cursor-paper-stats">
              <div><strong>36</strong><small>scenarios</small></div>
              <div><strong>4</strong><small>domains</small></div>
              <div><strong>A0-A2</strong><small>adversary levels</small></div>
            </div>
            <p>Healthcare · Finance · Legal · Corporate. AgentRisk is the severity-weighted score defined in the paper.</p>
          </Link>
        </section>

        <section className="cursor-faq" id="faq">
          <header><p className="cursor-eyebrow">FAQ</p><h2>Questions, answered.</h2></header>
          <div className="cursor-faq-list">
            {FAQ_ITEMS.map(([q, a]) => <FaqItem key={q} q={q} a={a} />)}
          </div>
        </section>

        <section className="cursor-final-cta">
          <div className="cursor-final-inner">
            <p className="cursor-eyebrow">Ready when you are</p>
            <h2>Test the path, not only the answer.</h2>
            <p>Create a local workspace, run a bundled scenario, then wire AgentLeak into CI or let your agent onboard itself.</p>
            <div className="cursor-actions">
              <Link className="cursor-button cursor-button-dark" to="/register">Create a workspace <Arrow /></Link>
              <Link className="cursor-button cursor-button-light" to="/docs/agents">Agents: discover and onboard <Arrow /></Link>
            </div>
            <p className="cursor-final-subactions">
              Prefer the source? <a href={REPO_URL}>View it on GitHub</a>.
            </p>
          </div>
        </section>
      </main>
      <SiteFooter />
      <nav className="sr-only" aria-label="Feature pages">
        {FEATURE_PAGES.map((page) => <Link key={page.slug} to={`/features/${page.slug}`}>{page.title}</Link>)}
      </nav>
    </div>
  )
}
