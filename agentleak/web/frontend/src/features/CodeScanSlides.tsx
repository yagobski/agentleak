import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Flower2 } from "lucide-react"
import { AGENTLEAK_MARK } from "@/features/ProductWorkflowCards"

const AUTOMATIONS = [
  ["Scan every pull request", "Run AgentLeak static analysis on pull requests and merge queues before sensitive code lands."],
  ["Auto-gate risky changes", "Fail CI automatically when the code privacy score falls below the threshold set for the repository."],
  ["Branch-specific policies", "Apply stricter secret, PII and third-party-send rules to production and release branches."],
  ["Review remediation status", "Keep findings, reviewers and the current privacy gate attached to the exact commit in GitHub."],
]

const PRODUCT_LINKS = [
  ["Make privacy operations self-driving", "/docs/agents"],
  ["Plan remediation from finding to release", "/features/trace-analysis"],
  ["Make code risk diffs effortless", "/features/code-scan"],
  ["Understand exposure at scale", "/features/agentrisk"],
]

function CodeScanIsometric() {
  const [markup, setMarkup] = useState("")

  useEffect(() => {
    let active = true
    fetch("/assets/brand/code-scan-automation.html")
      .then((response) => response.text())
      .then((source) => {
        const document = new DOMParser().parseFromString(source, "text/html")
        const svg = document.querySelector<SVGSVGElement>('svg[viewBox="0 0 464 537"]')
        const topPlate = svg?.querySelectorAll("g[filter]")[1]
        topPlate?.querySelectorAll('path[stroke="#8A8F98"]').forEach((path) => path.remove())

        if (svg && topPlate) {
          const mark = document.createElementNS("http://www.w3.org/2000/svg", "path")
          mark.setAttribute("class", "code-scan-agentleak-outline")
          mark.setAttribute("d", AGENTLEAK_MARK)
          mark.setAttribute("transform", "translate(187 76) scale(.35 .19) translate(0 -73)")
          mark.setAttribute("fill", "none")
          mark.setAttribute("stroke", "#8A8F98")
          mark.setAttribute("stroke-width", ".8")
          mark.setAttribute("vector-effect", "non-scaling-stroke")
          topPlate.appendChild(mark)
          svg.setAttribute("class", "code-scan-isometric-svg")
          if (active) setMarkup(svg.outerHTML)
        }
      })
      .catch(() => undefined)
    return () => { active = false }
  }, [])

  return <div className="code-scan-isometric" role="img" aria-label="AgentLeak and GitHub connected through an animated code privacy workflow" dangerouslySetInnerHTML={{ __html: markup }} />
}

export function CodeScanAutomationSlide() {
  return (
    <section className="code-scan-automation-section" aria-labelledby="code-scan-automation-title">
      <header>
        <p className="cursor-eyebrow">GitHub-native privacy automation</p>
        <h2 id="code-scan-automation-title">Turn every code change into a privacy checkpoint.</h2>
      </header>
      <div className="code-scan-automation-frame">
        <CodeScanIsometric />
        <div className="code-scan-automation-list">
          {AUTOMATIONS.map(([title, body]) => (
            <article key={title}>
              <h3>{title}</h3>
              <p>{body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

export function CodeScanProductSlide() {
  return (
    <section className="code-scan-product-slide" aria-labelledby="code-scan-product-title">
      <h2 id="code-scan-product-title" className="sr-only">Make privacy operations self-driving</h2>
      <nav aria-label="AgentLeak product workflows">
        {PRODUCT_LINKS.map(([title, href]) => (
          <Link key={title} to={href}>
            <strong>{title}</strong>
            <span>Learn more <i aria-hidden="true">→</i></span>
          </Link>
        ))}
      </nav>
      <div className="code-scan-product-quotes">
        <blockquote>
          <p>“A privacy issue gets fixed when the finding is tied to the exact file, line, trace and release gate.”</p>
          <footer>
            <span className="code-scan-client-symbol" aria-hidden="true"><img src="/assets/integrations/cursor.svg" alt="" /></span>
            <span><b>Code-to-trace evidence</b><small>One remediation path from source to runtime</small></span>
          </footer>
        </blockquote>
        <blockquote>
          <p>“Teams should not have to choose between shipping quickly and proving that agents handle sensitive data safely.”</p>
          <footer>
            <span className="code-scan-client-symbol" aria-hidden="true"><Flower2 /></span>
            <span><b>Fast, auditable releases</b><small>AgentLeak product principle</small></span>
          </footer>
        </blockquote>
      </div>
    </section>
  )
}
