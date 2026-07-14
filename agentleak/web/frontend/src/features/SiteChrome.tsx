import { useEffect, useState } from "react"
import { Link, useLocation } from "react-router-dom"
import { Menu, Monitor, Moon, Sun, X } from "lucide-react"

export const PAPER_URL = "https://arxiv.org/abs/2602.11510"
export const REPO_URL = "https://github.com/yagobski/agentleak-oss"

/** Per-page SEO: title + meta description, restored on unmount. */
export function usePageMeta(title: string, description: string) {
  useEffect(() => {
    const prevTitle = document.title
    document.title = title
    let meta = document.querySelector<HTMLMetaElement>('meta[name="description"]')
    if (!meta) {
      meta = document.createElement("meta")
      meta.name = "description"
      document.head.appendChild(meta)
    }
    const prevDesc = meta.content
    meta.content = description
    return () => {
      document.title = prevTitle
      if (meta) meta.content = prevDesc
    }
  }, [title, description])
}

type SiteTheme = "system" | "light" | "dark"

function applySiteTheme(theme: SiteTheme) {
  const prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches
  const light = theme === "light" || (theme === "system" && prefersLight)
  document.documentElement.toggleAttribute("data-site-theme", light)
  if (light) document.documentElement.setAttribute("data-site-theme", "light")
}

/** Cursor-style three-state theme switch, persisted per browser. */
export function ThemeSwitch() {
  const [theme, setTheme] = useState<SiteTheme>(
    () => (localStorage.getItem("agentleak-site-theme") as SiteTheme) || "dark",
  )
  useEffect(() => {
    localStorage.setItem("agentleak-site-theme", theme)
    applySiteTheme(theme)
    if (theme !== "system") return
    const media = window.matchMedia("(prefers-color-scheme: light)")
    const onChange = () => applySiteTheme("system")
    media.addEventListener("change", onChange)
    return () => media.removeEventListener("change", onChange)
  }, [theme])
  const options: { value: SiteTheme; icon: React.ReactNode; label: string }[] = [
    { value: "system", icon: <Monitor />, label: "System theme" },
    { value: "light", icon: <Sun />, label: "Light theme" },
    { value: "dark", icon: <Moon />, label: "Dark theme" },
  ]
  return (
    <div className="cursor-theme-switch" role="radiogroup" aria-label="Color theme">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={theme === option.value}
          aria-label={option.label}
          data-active={theme === option.value}
          onClick={() => setTheme(option.value)}
        >
          {option.icon}
        </button>
      ))}
    </div>
  )
}

export function Brand() {
  return (
    <Link to="/" className="cursor-brand" aria-label="AgentLeak home">
      <span className="cursor-brand-mark" aria-hidden="true"><i /><i /><i /></span>
      <span>AGENTLEAK</span>
    </Link>
  )
}

export const FEATURE_PAGES = [
  { slug: "trace-analysis", title: "Trace analysis", blurb: "Every channel of a run, audited" },
  { slug: "agentrisk", title: "AgentRisk scoring", blurb: "A deterministic score teams can explain" },
  { slug: "ci-gate", title: "CI policy gate", blurb: "Privacy as a required check" },
  { slug: "agent-api", title: "Agent API", blurb: "Agents test and fix themselves" },
] as const

/** Shared FAQ, rendered on the landing page and on the dedicated /faq page. */
export const FAQ_ITEMS: readonly (readonly [string, string])[] = [
  ["Is AgentLeak really open source?", "Yes. The analyzer and platform are MIT-licensed on GitHub. The core runs fully local with no telemetry, and you can self-host the hosted platform with one docker compose command."],
  ["How is this different from a guardrail or a red-team prompt?", "Guardrails and red-team prompts look at inputs and the final output. AgentLeak audits the whole execution trace, so it catches data that leaked into a tool call, shared memory, a log or a generated file even when the final answer looks clean."],
  ["What is AgentRisk?", "A deterministic, severity-weighted score from 0 to 1, defined in the published benchmark. The same trace always yields the same score, so a regression in CI means the agent changed, not the judge. It comes with a 0 to 100 privacy score for readability."],
  ["Do I need to send data to a hosted model?", "No. Free detection (regex, Presidio, entropy, de-obfuscation) runs locally at no cost. The LLM-judge and live agent runs are bring-your-own-key, so the platform never spends its own money and never sees data you did not send it."],
  ["Which frameworks does it work with?", "Traces from LangChain, LangGraph, CrewAI, MCP servers and OpenTelemetry all normalize to one AgentLeak schema. Any OpenAI-style chat log is accepted directly, and a generic trace format covers everything else."],
  ["Is it free for autonomous agents?", "Yes. An agent can onboard in one call and use the free detection tiers within a generous monthly quota, with no human in the loop. Discovery is machine-readable at /llms.txt."],
  ["How do I add it to CI?", "Run the CLI in any pipeline. It exits non-zero when a run crosses the policy you set for the project, so a failing privacy gate blocks the merge like any failing test. On GitHub or GitLab it reports back as a normal required status check with the trace attached."],
  ["What happens to my traces and data?", "Nothing leaves your machine on the local and self-hosted paths. There is no telemetry and no phone-home. On the hosted instance, raw sensitive values are never stored: findings reference channels and severity, not the secrets themselves."],
  ["Can I self-host the whole platform?", "Yes. One docker compose command brings up the same platform the hosted instance runs, on your own infrastructure or in your VPC. Self-hosting removes the free-tier quota entirely."],
  ["Which compliance frameworks does it map to?", "Each run carries a compliance posture across GDPR, Quebec Law 25, HIPAA and the OWASP LLM Top 10, so a finding is tied to the obligation it touches, not just a generic severity label."],
] as const

export const FAQ_GROUPS: readonly { title: string; items: readonly (readonly [string, string])[] }[] = [
  { title: "The basics", items: FAQ_ITEMS.slice(0, 3) },
  { title: "Running it", items: FAQ_ITEMS.slice(3, 7) },
  { title: "Data, hosting and compliance", items: FAQ_ITEMS.slice(7) },
] as const

/** Single accordion row for the FAQ. */
export function FaqItem({ q, a }: { q: string; a: string }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="cursor-faq-item" data-open={open}>
      <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        <span>{q}</span><i aria-hidden="true">{open ? "–" : "+"}</i>
      </button>
      {open && <p>{a}</p>}
    </div>
  )
}

export function SiteNav() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  // Close the mobile menu on navigation and lock body scroll while it is open.
  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : ""
    return () => {
      document.body.style.overflow = ""
    }
  }, [mobileOpen])

  return (
    <header className="cursor-nav">
      <Brand />
      <nav aria-label="Main navigation">
        <div className="cursor-nav-item">
          <Link to="/features/trace-analysis">Product</Link>
          <div className="cursor-nav-menu" role="menu">
            {FEATURE_PAGES.map((page) => (
              <Link key={page.slug} to={`/features/${page.slug}`} role="menuitem">
                <b>{page.title}</b><small>{page.blurb}</small>
              </Link>
            ))}
          </div>
        </div>
        <div className="cursor-nav-item">
          <Link to="/docs">Resources</Link>
          <div className="cursor-nav-menu" role="menu">
            <Link to="/docs" role="menuitem"><b>Documentation</b><small>Concepts, guides and API</small></Link>
            <Link to="/research" role="menuitem"><b>Research</b><small>The papers behind the scores</small></Link>
            <Link to="/faq" role="menuitem"><b>FAQ</b><small>Short answers to common questions</small></Link>
            <a href={REPO_URL} role="menuitem"><b>GitHub</b><small>MIT-licensed source</small></a>
          </div>
        </div>
        <Link to="/research">Research</Link>
        <Link to="/docs">Documentation</Link>
      </nav>
      <div className="cursor-nav-actions">
        <a className="cursor-nav-gh" href={REPO_URL} aria-label="AgentLeak on GitHub">GitHub</a>
        <Link to="/login">Sign in</Link>
        <Link className="cursor-pill cursor-pill-dark" to="/register">Start testing</Link>
        <button
          type="button"
          className="cursor-nav-burger"
          aria-label={mobileOpen ? "Close menu" : "Open menu"}
          aria-expanded={mobileOpen}
          onClick={() => setMobileOpen((open) => !open)}
        >
          {mobileOpen ? <X /> : <Menu />}
        </button>
      </div>
      {mobileOpen && (
        <div className="cursor-nav-mobile" role="dialog" aria-label="Menu">
          <span>Product</span>
          {FEATURE_PAGES.map((page) => (
            <Link key={page.slug} to={`/features/${page.slug}`}>{page.title}</Link>
          ))}
          <span>Resources</span>
          <Link to="/docs">Documentation</Link>
          <Link to="/research">Research</Link>
          <Link to="/faq">FAQ</Link>
          <a href={REPO_URL}>GitHub</a>
          <div className="cursor-nav-mobile-actions">
            <Link className="cursor-button cursor-button-light" to="/login">Sign in</Link>
            <Link className="cursor-button cursor-button-dark" to="/register">Start testing</Link>
          </div>
        </div>
      )}
    </header>
  )
}

export function SiteFooter() {
  return (
    <footer className="cursor-footer">
      <div className="cursor-footer-grid">
        <Brand />
        <div><h3>Product</h3>{FEATURE_PAGES.map((page) => <Link key={page.slug} to={`/features/${page.slug}`}>{page.title}</Link>)}</div>
        <div><h3>Resources</h3><Link to="/docs">Documentation</Link><Link to="/research">Research</Link><Link to="/faq">FAQ</Link><Link to="/docs/agents">For agents</Link></div>
        <div><h3>Open source</h3><a href={REPO_URL}>GitHub</a><a href="/openapi.json">OpenAPI</a><a href="/llms.txt">llms.txt</a><a href={PAPER_URL}>arXiv:2602.11510</a></div>
      </div>
      <div className="cursor-footer-bar">
        <p>© 2026 AgentLeak · MIT licensed</p>
        <ThemeSwitch />
      </div>
    </footer>
  )
}
