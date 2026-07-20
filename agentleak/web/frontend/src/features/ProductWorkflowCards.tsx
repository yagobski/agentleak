import { useEffect, useState } from "react"
import {
  Activity,
  Bot,
  Braces,
  Cloud,
  Database,
  FileText,
  GitBranch,
  Mail,
  MessageSquare,
  Network,
  Radio,
  Webhook,
  type LucideIcon,
} from "lucide-react"

const INTEGRATIONS: Array<{ label: string; icon: LucideIcon; active?: boolean }> = [
  { label: "OpenTelemetry", icon: Activity },
  { label: "Agent framework", icon: Bot },
  { label: "Structured traces", icon: Braces },
  { label: "Cloud runtime", icon: Cloud },
  { label: "MCP", icon: Network, active: true },
  { label: "Webhook", icon: Webhook, active: true },
  { label: "Shared memory", icon: Database, active: true },
  { label: "CI pipeline", icon: GitBranch, active: true },
  { label: "Logs", icon: Radio },
  { label: "Email", icon: Mail },
  { label: "Agent messages", icon: MessageSquare },
  { label: "Generated files", icon: FileText },
]

function AgentRunVisual() {
  const [markup, setMarkup] = useState("")

  useEffect(() => {
    let active = true
    fetch("/assets/brand/agent-call-workflow.html")
      .then((response) => response.text())
      .then((source) => {
        if (active) setMarkup(source)
      })
      .catch(() => undefined)
    return () => { active = false }
  }, [])

  return (
    <div className="workflow-call-visual" aria-label="An agent run flowing into AgentLeak for automatic privacy analysis" role="img">
      {markup && <div className="workflow-supplied-svg" aria-hidden="true" dangerouslySetInnerHTML={{ __html: markup }} />}
      <div className="workflow-agentleak-node" aria-hidden="true"><span /></div>
    </div>
  )
}

function IntegrationVisual() {
  return (
    <div className="workflow-integration-visual" role="img" aria-label="Execution signals from twelve sources normalized by AgentLeak">
      <div className="workflow-integration-grid">
        {INTEGRATIONS.map(({ label, icon: Icon, active }) => (
          <span key={label} data-active={active || undefined} title={label}><Icon aria-hidden /></span>
        ))}
      </div>
      <div className="workflow-grid-glow" aria-hidden="true" />
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
