// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Monitor, Moon, Sun } from "lucide-react"
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
