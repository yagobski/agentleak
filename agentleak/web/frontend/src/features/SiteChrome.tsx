import { useEffect, useState } from "react"
import { Link, useLocation } from "react-router-dom"
import { Menu, Monitor, Moon, Sun, X } from "lucide-react"
import { AgentLeakLogo } from "@/features/AgentLeakLogo"

export const PAPER_URL = "https://arxiv.org/abs/2602.11510"
export const REPO_URL = "https://github.com/yagobski/agentleak"
export const SITE_URL = "https://www.agentleak.org"

type PageMetaOptions = {
  noIndex?: boolean
  type?: "website" | "article"
  structuredData?: Record<string, unknown>
}

/** Canonical, social and crawler metadata for each public route. */
// Filled during a server render so the build-time prerender can read the exact
// metadata a page declares for itself. One source of truth: whatever a page
// passes here ends up both in the static HTML and in the client-side updates.
export const ssrMeta: { title: string; description: string; options: PageMetaOptions } = {
  title: "",
  description: "",
  options: {},
}

export function usePageMeta(title: string, description: string, options: PageMetaOptions = {}) {
  if (typeof document === "undefined") {
    ssrMeta.title = title
    ssrMeta.description = description
    ssrMeta.options = options
  }
  const structuredData = options.structuredData ? JSON.stringify(options.structuredData) : ""
  useEffect(() => {
    document.title = title
    const canonicalUrl = `${SITE_URL}${window.location.pathname === "/" ? "/" : window.location.pathname}`
    const setMeta = (attribute: "name" | "property", key: string, content: string) => {
      let element = document.head.querySelector<HTMLMetaElement>(`meta[${attribute}="${key}"]`)
      if (!element) {
        element = document.createElement("meta")
        element.setAttribute(attribute, key)
        document.head.appendChild(element)
      }
      element.content = content
    }
    setMeta("name", "description", description)
    setMeta("name", "robots", options.noIndex ? "noindex, nofollow" : "index, follow, max-image-preview:large")
    setMeta("property", "og:title", title)
    setMeta("property", "og:description", description)
    setMeta("property", "og:type", options.type ?? "website")
    setMeta("property", "og:url", canonicalUrl)
    setMeta("property", "og:site_name", "AgentLeak")
    setMeta("property", "og:locale", "en_US")
    setMeta("name", "twitter:card", "summary_large_image")
    setMeta("property", "og:image", `${SITE_URL}/og.png`)
    setMeta("name", "twitter:image", `${SITE_URL}/og.png`)
    setMeta("name", "twitter:title", title)
    setMeta("name", "twitter:description", description)

    let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]')
    if (!canonical) {
      canonical = document.createElement("link")
      canonical.rel = "canonical"
      document.head.appendChild(canonical)
    }
    canonical.href = canonicalUrl

    const schemaId = "agentleak-page-schema"
    document.getElementById(schemaId)?.remove()
    if (structuredData) {
      const schema = document.createElement("script")
      schema.id = schemaId
      schema.type = "application/ld+json"
      schema.text = structuredData.replace(/</g, "\\u003c")
      document.head.appendChild(schema)
    }
  }, [description, options.noIndex, options.type, structuredData, title])
}

type SiteTheme = "system" | "light" | "dark"

function applySiteTheme(theme: SiteTheme) {
  if (typeof window === "undefined") return
  const prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches
  const light = theme === "light" || (theme === "system" && prefersLight)
  document.documentElement.toggleAttribute("data-site-theme", light)
  if (light) document.documentElement.setAttribute("data-site-theme", "light")
}

/** Cursor-style three-state theme switch, persisted per browser. */
export function ThemeSwitch() {
  const [theme, setTheme] = useState<SiteTheme>(
    () =>
      typeof window === "undefined"
        ? "dark"
        : (localStorage.getItem("agentleak-site-theme") as SiteTheme) || "dark",
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
      <AgentLeakLogo className="agentleak-logo-site" label="" />
    </Link>
  )
}

export const FEATURE_PAGES = [
  { slug: "trace-analysis", title: "Trace analysis", blurb: "Every channel of a run, audited" },
  { slug: "agentrisk", title: "AgentRisk scoring", blurb: "A deterministic score teams can explain" },
  { slug: "code-scan", title: "Static code scan", blurb: "Catch secrets before the agent runs" },
  { slug: "red-team", title: "Adversarial red-team", blurb: "Replay real attack classes, not just clean traces" },
  { slug: "ci-gate", title: "CI policy gate", blurb: "Privacy as a required check" },
  { slug: "agent-api", title: "Agent API", blurb: "Agents test and fix themselves" },
] as const

/** Shared FAQ content rendered inside the landing and feature pages. */
export const FAQ_ITEMS: readonly (readonly [string, string])[] = [
  ["Is AgentLeak really open source?", "Yes. The analyzer and platform are MIT-licensed on GitHub. The core runs fully local with no telemetry, and you can self-host the hosted platform with one docker compose command."],
  ["How is this different from a guardrail or a red-team prompt?", "Guardrails and red-team prompts look at inputs and the final output. AgentLeak audits the whole execution trace, so it catches data that leaked into a tool call, shared memory, a log or a generated file even when the final answer looks clean."],
  ["What is AgentRisk?", "A deterministic, severity-weighted score from 0 to 1, defined in the published benchmark. The same trace always yields the same score, so a regression in CI means the agent changed, not the judge. It comes with a 0 to 100 privacy score for readability."],
  ["Do I need to send data to a hosted model?", "No. Free detection (regex, Presidio, entropy, de-obfuscation) runs locally at no cost. The LLM-judge and live agent runs are bring-your-own-key, so the platform never spends its own money and never sees data you did not send it."],
  ["Which frameworks does it work with?", "Traces from LangChain, LangGraph, CrewAI, MCP servers and OpenTelemetry all normalize to one AgentLeak schema. Any OpenAI-style chat log is accepted directly, and a generic trace format covers everything else."],
  ["Is it free for autonomous agents?", "Yes. An agent can onboard in one call and use the free detection tiers within a generous monthly quota, with no human in the loop. Discovery is machine-readable at /llms.txt."],
  ["How do I add it to CI?", "Run the CLI in any pipeline with a --fail-under threshold. It exits non-zero when a run crosses the policy you set for the project, so GitHub Actions, GitLab CI or any runner treats it as a failing job automatically. Mark that job required in branch protection and the merge blocks itself \u2014 no bespoke GitHub or GitLab integration to install."],
  ["What happens to my traces and data?", "Nothing leaves your machine on the local and self-hosted paths. There is no telemetry and no phone-home. On the hosted instance, raw sensitive values are never stored: findings reference channels and severity, not the secrets themselves."],
  ["Can I self-host the whole platform?", "Yes. One docker compose command brings up the same platform the hosted instance runs, on your own infrastructure or in your VPC. Self-hosting removes the free-tier quota entirely."],
  ["Which compliance frameworks does it map to?", "Each run carries a compliance posture across all 7 frameworks the scoring engine understands: GDPR, Quebec Law 25, NIST AI RMF, the OWASP LLM Top 10, the EU AI Act, HIPAA and PCI-DSS v4.0. A finding is tied to the specific obligation it touches, not a generic severity label \u2014 this is a mapping to help a review, not a certification or legal attestation of compliance."],
  ["What counts against the free quota?", "Only metered actions on the hosted platform: a run analysis, a live agent turn or a self-test call. Local CLI and self-hosted usage have no quota at all, and reading reports or browsing the dashboard never counts."],
  ["Can I bring my own detection rules or PII types?", "Yes. The regex and entropy detectors accept a project-level ruleset, so you can add a proprietary ID format or an internal secret pattern alongside the built-in email, key and PHI/PII detectors."],
  ["Does it handle multi-agent and A2A traces?", "Yes. Inter-agent messages and hand-offs are their own channel, so a leak that only appears when one agent hands a task to another is caught the same way a leaked tool call would be."],
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
          <Link to="/features">Product</Link>
          <div className="cursor-nav-menu" role="menu">
            {FEATURE_PAGES.map((page) => (
              <Link key={page.slug} to={`/features/${page.slug}`} role="menuitem">
                <b>{page.title}</b><small>{page.blurb}</small>
              </Link>
            ))}
          </div>
        </div>
        <div className="cursor-nav-item">
          <Link to="/use-cases/multi-agent-privacy">Solutions</Link>
          <div className="cursor-nav-menu" role="menu">
            <Link to="/use-cases/multi-agent-privacy" role="menuitem"><b>Multi-agent privacy</b><small>Trace leaks across handoffs and memory</small></Link>
            <Link to="/security" role="menuitem"><b>Security architecture</b><small>Local execution, redaction and isolation</small></Link>
            <Link to="/integrations" role="menuitem"><b>Integrations</b><small>Frameworks, repositories, telemetry and CI</small></Link>
          </div>
        </div>
        <Link to="/research">Research</Link>
        <Link to="/benchmark">Benchmark</Link>
        <Link to="/compare">Compare</Link>
        <Link to="/integrations">Integrations</Link>
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
          <span>Solutions</span>
          <Link to="/use-cases/multi-agent-privacy">Multi-agent privacy</Link>
          <Link to="/security">Security architecture</Link>
          <span>Resources</span>
          <Link to="/integrations">Integrations</Link>
          <Link to="/docs">Documentation</Link>
          <Link to="/research">Research</Link>
          <Link to="/benchmark">Benchmark</Link>
          <Link to="/compare">Compare</Link>
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
        <div><h3>Resources</h3><Link to="/integrations">Integrations</Link><Link to="/docs">Documentation</Link><Link to="/docs/getting-started">Getting started</Link><Link to="/docs/integrations">Integration guides</Link><Link to="/docs/scoring">Scoring</Link><Link to="/research">Research</Link><Link to="/benchmark">Benchmark</Link><Link to="/compare">AgentLeak vs alternatives</Link><Link to="/compliance/eu-ai-act">EU AI Act</Link></div>
        <div><h3>Company</h3><Link to="/about">About</Link><Link to="/security">Security</Link><Link to="/use-cases/multi-agent-privacy">Multi-agent privacy</Link><Link to="/#faq">Questions</Link></div>
        <div><h3>Open source</h3><a href={REPO_URL}>GitHub</a><a href="/openapi.json">OpenAPI</a><a href="/llms.txt">llms.txt</a><a href={PAPER_URL}>arXiv:2602.11510</a></div>
      </div>
      <div className="cursor-footer-bar">
        <p>© 2026 AgentLeak · MIT licensed</p>
        <ThemeSwitch />
      </div>
    </footer>
  )
}
