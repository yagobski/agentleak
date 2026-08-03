/**
 * Build-time server entry.
 *
 * The site is a client-rendered SPA, which means a crawler that does not run
 * JavaScript sees an empty shell — no headings, no copy, and the same <title>
 * on every route. This entry renders the logged-out routes to real HTML at
 * build time so search engines, LLM crawlers and link unfurlers get the page
 * itself. The browser still boots the SPA on top; this only changes what
 * arrives before JavaScript does.
 */
import { StaticRouter } from "react-router-dom/server"
import { renderToString } from "react-dom/server"
import { TooltipProvider } from "@/components/ui/tooltip"
import { PublicRoutes } from "./PublicRoutes"
import { ssrMeta } from "@/features/SiteChrome"

export type RenderedPage = {
  html: string
  title: string
  description: string
  canonicalPath: string
  type: string
  noIndex: boolean
  structuredData: string
}

export function render(url: string): RenderedPage {
  ssrMeta.title = ""
  ssrMeta.description = ""
  ssrMeta.options = {}

  const html = renderToString(
    <TooltipProvider delayDuration={200}>
      <StaticRouter location={url}>
        <PublicRoutes />
      </StaticRouter>
    </TooltipProvider>,
  )

  const options = ssrMeta.options ?? {}
  return {
    html,
    title: ssrMeta.title,
    description: ssrMeta.description,
    canonicalPath: url,
    type: options.type ?? "website",
    noIndex: Boolean(options.noIndex),
    structuredData: options.structuredData ? JSON.stringify(options.structuredData) : "",
  }
}
