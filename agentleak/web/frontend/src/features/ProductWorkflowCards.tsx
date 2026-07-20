import { useEffect, useState } from "react"

const AGENTLEAK_MARK = "M254.055 120.935C254.055 120.935 221.678 112.525 189.301 99.4902C160.288 87.7168 136.32 73 136.32 73C136.32 73 112.773 88.1373 83.3397 99.4902C51.3832 112.525 19.0062 120.514 18.5857 120.935C16.0629 135.231 14.8014 150.368 14.8014 165.506C14.8014 168.869 14.8014 170.551 15.2219 173.915C16.9038 191.996 48.8603 183.166 60.2133 178.961C61.4747 178.54 63.1566 177.7 64.4181 177.279C68.6229 175.597 72.8277 173.915 77.4529 171.813C86.283 168.028 95.5336 163.403 105.205 158.357C119.08 150.789 133.377 142.379 145.571 132.708C127.49 157.096 88.8059 186.109 45.4965 204.61C34.564 209.236 19.4267 215.122 8.91471 214.702C-3.69969 214.281 0.505106 216.384 1.34607 216.804C14.8014 223.532 22.3701 233.203 26.1544 242.033C28.6773 247.92 37.5073 257.17 85.0216 232.782C111.932 218.907 146.412 199.144 181.312 171.392C182.573 170.551 183.834 169.29 185.096 168.449C192.664 162.142 200.654 155.835 208.222 149.107C190.142 185.689 139.264 228.157 77.8734 259.693C58.5313 269.785 53.4856 271.046 45.076 273.989C33.723 277.774 22.7905 276.092 22.7905 278.194C22.3701 281.138 37.0869 284.081 52.2242 299.218C66.1 313.094 101 297.116 115.717 289.127C132.115 279.876 161.549 261.375 181.312 244.135C185.096 240.772 188.46 237.408 191.824 234.044C177.107 268.944 145.571 294.172 103.943 317.719C93.4312 323.606 75.771 328.652 68.2024 330.754C66.1 331.595 63.1566 331.595 63.1566 332.857C63.1566 335.38 79.9758 337.061 90.9083 342.948C106.046 350.937 116.558 355.142 120.342 356.404C125.388 358.506 130.854 359.767 136.32 361.029C208.643 345.051 257.418 262.216 257.418 165.085C257.839 150.368 256.577 135.231 254.055 120.935Z"

function AgentRunVisual() {
  const [markup, setMarkup] = useState("")

  useEffect(() => {
    let active = true
    fetch("/assets/brand/agent-call-workflow.html")
      .then((response) => response.text())
      .then((source) => {
        const agentLeakSymbol = `<path fill="url(#_S_15_y)" transform="translate(468 163) scale(.218)" d="${AGENTLEAK_MARK}"></path>`
        const exactSvgWithAgentLeak = source.replace(/<path fill="url\(#_S_15_y\)"[\s\S]*?(?=<defs>)/, agentLeakSymbol)
        if (active) setMarkup(exactSvgWithAgentLeak)
      })
      .catch(() => undefined)
    return () => { active = false }
  }, [])

  return (
    <div className="workflow-call-visual" aria-label="An agent run flowing into AgentLeak for automatic privacy analysis" role="img">
      {markup && <div className="workflow-supplied-svg" aria-hidden="true" dangerouslySetInnerHTML={{ __html: markup }} />}
    </div>
  )
}

function IntegrationVisual() {
  return (
    <div className="workflow-integration-visual" role="img" aria-label="Execution signals from connected tools normalized into an AgentLeak trace">
      <img src="/assets/brand/trace-integrations.png" alt="" width="672" height="424" loading="lazy" decoding="async" />
      <svg className="workflow-image-mask" viewBox="0 0 672 424" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id="agentleak-mask-top" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#08090A" /><stop offset="15%" stopColor="#08090A" /><stop offset="50%" stopColor="#08090A" stopOpacity="0" /></linearGradient>
          <linearGradient id="agentleak-mask-bottom" x1="0" y1="1" x2="0" y2="0"><stop offset="0%" stopColor="#08090A" /><stop offset="15%" stopColor="#08090A" /><stop offset="50%" stopColor="#08090A" stopOpacity="0" /></linearGradient>
          <linearGradient id="agentleak-mask-left" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor="#08090A" /><stop offset="15%" stopColor="#08090A" /><stop offset="50%" stopColor="#08090A" stopOpacity="0" /></linearGradient>
          <linearGradient id="agentleak-mask-right" x1="1" y1="0" x2="0" y2="0"><stop offset="0%" stopColor="#08090A" /><stop offset="15%" stopColor="#08090A" /><stop offset="50%" stopColor="#08090A" stopOpacity="0" /></linearGradient>
        </defs>
        <rect width="672" height="424" fill="url(#agentleak-mask-top)" /><rect width="672" height="424" fill="url(#agentleak-mask-bottom)" />
        <rect width="672" height="424" fill="url(#agentleak-mask-left)" /><rect width="672" height="424" fill="url(#agentleak-mask-right)" />
      </svg>
    </div>
  )
}

export function ProductWorkflowCards() {
  return (
    <section className="workflow-section" aria-labelledby="workflow-title">
      <header>
        <p className="cursor-eyebrow">From execution to evidence</p>
        <h2 id="workflow-title">Turn every agent signal into a privacy action.</h2>
      </header>
      <div className="workflow-cards">
        <article>
          <AgentRunVisual />
          <div className="workflow-caption">
            <h3>Auto-create findings from agent runs</h3>
            <p>Capture disclosures from tool calls, memory and handoffs, then create trace-linked remediation without prompts or manual review.</p>
          </div>
        </article>
        <article>
          <IntegrationVisual />
          <div className="workflow-caption">
            <h3>Create privacy tests from every execution surface</h3>
            <p>Ingest frameworks, OpenTelemetry, MCP, logs and CI, then normalize every source into one auditable AgentLeak run.</p>
          </div>
        </article>
      </div>
    </section>
  )
}
