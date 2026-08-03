/**
 * Emit real HTML for every public route.
 *
 * Reads the SPA shell produced by `vite build`, renders each marketing/docs
 * route with the SSR bundle, and writes `<route>/index.html` next to it. FastAPI
 * serves those files when it has one, and falls back to the shell otherwise, so
 * a new route degrades to today's behaviour rather than 404ing.
 *
 * Metadata is not duplicated here: each page declares it through `usePageMeta`,
 * and the SSR render reports back what it declared.
 */
import { mkdir, readFile, writeFile } from "node:fs/promises"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const HERE = dirname(fileURLToPath(import.meta.url))
const STATIC_DIR = join(HERE, "../../static")
// Prerendered pages live in their own tree: the SPA shell stays untouched as
// the fallback, and a route without a prerendered file simply keeps working.
const OUT_DIR = join(STATIC_DIR, "_prerendered")
const SITE_URL = "https://www.agentleak.org"

// Every route a logged-out visitor can reach. Redirect-only routes are left
// out: prerendering a redirect would hand a crawler a dead end.
export const ROUTES = [
  "/",
  "/features",
  "/features/trace-analysis",
  "/features/agentrisk",
  "/features/code-scan",
  "/features/red-team",
  "/features/ci-gate",
  "/features/agent-api",
  "/integrations",
  "/security",
  "/use-cases/multi-agent-privacy",
  "/about",
  "/research",
  "/benchmark",
  "/compare",
  "/compliance/eu-ai-act",
  "/docs",
  "/docs/getting-started",
  "/docs/integrations",
  "/docs/scoring",
  "/docs/developers",
  "/docs/agents",
  "/docs/api",
  "/docs/privacy-compliance",
  "/docs/red-team",
  "/docs/red-team/configuration",
  "/docs/red-team/architecture",
  "/docs/red-team/vulnerabilities",
  "/docs/red-team/plugins",
  "/docs/red-team/strategies",
  "/docs/ci-cd",
]

const escapeAttr = (value) =>
  String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;")

function head(page) {
  const url = `${SITE_URL}${page.canonicalPath === "/" ? "/" : page.canonicalPath}`
  const title = escapeAttr(page.title || "AgentLeak — privacy tests for agent systems")
  const description = escapeAttr(page.description)
  const robots = page.noIndex ? "noindex, nofollow" : "index, follow, max-image-preview:large"
  const tags = [
    `<title>${title}</title>`,
    `<meta name="description" content="${description}" />`,
    `<meta name="robots" content="${robots}" />`,
    `<link rel="canonical" href="${url}" />`,
    `<meta property="og:title" content="${title}" />`,
    `<meta property="og:description" content="${description}" />`,
    `<meta property="og:type" content="${escapeAttr(page.type)}" />`,
    `<meta property="og:url" content="${url}" />`,
    `<meta property="og:site_name" content="AgentLeak" />`,
    `<meta property="og:locale" content="en_US" />`,
    `<meta property="og:image" content="${SITE_URL}/og.png" />`,
    `<meta property="og:image:width" content="1200" />`,
    `<meta property="og:image:height" content="630" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    `<meta name="twitter:title" content="${title}" />`,
    `<meta name="twitter:description" content="${description}" />`,
    `<meta name="twitter:image" content="${SITE_URL}/og.png" />`,
  ]
  if (page.structuredData) {
    // Escaping "<" keeps a payload from closing the script tag early.
    tags.push(
      `<script type="application/ld+json">${page.structuredData.replace(/</g, "\\u003c")}</script>`,
    )
  }
  return tags.join("\n    ")
}

async function main() {
  const { render } = await import(join(HERE, "../.prerender/entry-prerender.js"))
  const shell = await readFile(join(STATIC_DIR, "index.html"), "utf8")

  let written = 0
  for (const route of ROUTES) {
    let page
    try {
      page = render(route)
    } catch (error) {
      console.error(`  ✗ ${route}: ${error.message}`)
      process.exitCode = 1
      continue
    }

    // Swap the shell's default head block (title through twitter:description)
    // for this page's own, then drop the rendered markup into the mount point.
    const headStart = shell.indexOf("<title>")
    const headEnd = shell.indexOf('<meta name="theme-color"')
    if (headStart === -1 || headEnd === -1) {
      throw new Error("index.html shell changed shape; prerender head injection needs updating")
    }
    const html =
      shell.slice(0, headStart) +
      head(page) +
      "\n    " +
      shell.slice(headEnd).replace('<div id="root"></div>', `<div id="root">${page.html}</div>`)

    const dir = join(OUT_DIR, route === "/" ? "" : route)
    await mkdir(dir, { recursive: true })
    await writeFile(join(dir, "index.html"), html, "utf8")
    written += 1
  }
  console.log(`prerendered ${written}/${ROUTES.length} routes`)
}

main()
