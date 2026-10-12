// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { ArrowRight, Baseline, Bot, BriefcaseMedical, CheckCircle2, ChevronRight, FileJson2, FlaskConical, GraduationCap, Headset, Info, RotateCcw, Shield, Sparkles, TrendingUp, Users, Zap } from "lucide-react"
import { toast } from "sonner"
import { api, type AnalyzePayload, type Project, type Report, type Scenario } from "@/lib/api"
import { scoreColor } from "@/lib/format"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { AgentLeakMark } from "@/features/AgentLeakLogo"
import { ConfigPanel } from "@/features/ConfigPanel"
import { RedTeamView } from "@/features/RedTeamView"
import { ResultsView } from "@/features/ResultsView"
import { PageHeader } from "@/layout/AppShell"

const SCENARIO_ICONS: Record<string, typeof Bot> = {
  healthcare: BriefcaseMedical,
  finance: TrendingUp,
  education: GraduationCap,
  hr: Users,
  customer_support: Headset,
}

function QuickScenarioCard({ scenario, active, onSelect }: { scenario: Scenario; active?: boolean; onSelect: (id: string) => void }) {
  const domain = scenario.domain ?? "general"
  const Icon = SCENARIO_ICONS[domain] ?? Bot
  const rawTitle = scenario.name && scenario.name !== scenario.id
    ? scenario.name
    : scenario.id.replace(new RegExp(`^${domain}_`), "").replace(/_/g, " ")
  const title = rawTitle.charAt(0).toUpperCase() + rawTitle.slice(1)
  return (
    <button onClick={() => onSelect(scenario.id)} className={`group flex min-w-0 items-start gap-3 rounded-lg border bg-card p-4 text-left transition-all hover:border-primary/40 hover:shadow-sm ${active ? "border-primary/50 ring-1 ring-primary/20" : "border-border"}`}>
      <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary"><Icon className="size-3.5" /></div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-1"><span className="text-[13px] font-medium leading-snug">{title}</span><ChevronRight className="size-3.5 shrink-0 text-muted-foreground group-hover:text-primary" /></div>
        {scenario.description && <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">{scenario.description}</p>}
        <div className="mt-2 flex flex-wrap gap-1.5"><span className="rounded-full bg-muted px-2 py-0.5 text-[9px] font-medium text-muted-foreground">sample trace</span>{scenario.expected_outcome && <span className={`rounded-full px-2 py-0.5 text-[9px] font-medium ${scenario.expected_outcome === "clean" ? "bg-sev-ok/10 text-sev-ok" : "bg-sev-l4/10 text-sev-l4"}`}>expected: {scenario.expected_outcome}</span>}</div>
      </div>
    </button>
  )
}

function ModeGuide() {
  const steps = [
    { icon: FileJson2, title: "Analyze your trace", text: "Paste or import evidence captured from your own agent. AgentLeak scores the trace; it does not run the agent." },
    { icon: Sparkles, title: "Explore sample data", text: "Open a packaged clean or leaking trace to learn how findings and scores work. No agent is executed." },
    { icon: Zap, title: "Red-team a model", text: "Generate adversarial probes and run them in the AgentLeak test harness, either offline or with a configured model." },
  ]
  return (
    <div className="mb-5 grid gap-px overflow-hidden rounded-lg border border-border bg-border md:[grid-template-columns:repeat(3,minmax(0,1fr))]">
      {steps.map((step, index) => <div key={step.title} className="min-w-0 bg-card p-4"><div className="flex min-w-0 items-start gap-2"><span className="mt-0.5 shrink-0 font-mono text-[10px] text-muted-foreground">0{index + 1}</span><step.icon className="mt-0.5 size-4 shrink-0" /><p className="min-w-0 text-sm font-semibold leading-snug">{step.title}</p></div><p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">{step.text}</p></div>)}
    </div>
  )
}

function ComparisonBar({ baseline, current, onClear }: { baseline: Report; current: Report; onClear: () => void }) {
  const same = baseline === current
  const scoreDelta = current.privacy_score - baseline.privacy_score
  const riskDelta = current.risk_index - baseline.risk_index
  const findingsDelta = current.summary.total_findings - baseline.summary.total_findings
  return (
    <Card className="mb-4 overflow-hidden border-primary/25 bg-primary/[0.025]">
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div className="flex min-w-0 items-center gap-3"><Baseline className="size-4 shrink-0 text-primary" /><div className="min-w-0"><p className="text-xs font-semibold">{same ? "Baseline pinned" : "Candidate compared with baseline"}</p><p className="truncate text-[11px] text-muted-foreground">{same ? "Edit the trace or policy, then analyze again to measure the delta." : "Positive score and negative risk/finding deltas indicate an improvement."}</p></div></div>
        {!same && <div className="flex flex-wrap items-center gap-4 font-mono text-xs"><span style={{ color: scoreColor(current.privacy_score) }}>score {scoreDelta >= 0 ? "+" : ""}{scoreDelta.toFixed(0)}</span><span>RI {riskDelta >= 0 ? "+" : ""}{riskDelta.toFixed(3)}</span><span>findings {findingsDelta >= 0 ? "+" : ""}{findingsDelta}</span></div>}
        <Button variant="ghost" size="sm" onClick={onClear}><RotateCcw className="size-3.5" /> Clear baseline</Button>
      </div>
    </Card>
  )
}

function TargetReadiness({ project }: { project: Project }) {
  const agent = project.config.agent
  const agents = project.config.agents ?? []
  const hasPurpose = Boolean(project.description?.trim())
  const hasTarget = Boolean(agent?.model || agents.some((item) => item.endpoint?.model))
  const toolCount = agents.reduce((count, item) => count + (item.tools?.length ?? 0), 0)
  return (
    <Card className="mb-5 overflow-hidden">
      <div className="grid gap-4 p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
        <div className="min-w-0"><p className="text-sm font-semibold">Test configuration · {project.name}</p><p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{project.description || "Add the intended purpose and limits so campaign results can be interpreted against the right boundary."}</p></div>
        <div className="flex flex-wrap gap-2 text-[10px]"><span className={`rounded-full px-2 py-1 ${hasPurpose ? "bg-sev-ok/10 text-sev-ok" : "bg-sev-l2/10 text-sev-l2"}`}>{hasPurpose ? "purpose defined" : "purpose missing"}</span><span className={`rounded-full px-2 py-1 ${hasTarget ? "bg-sev-ok/10 text-sev-ok" : "bg-muted text-muted-foreground"}`}>{hasTarget ? "model endpoint ready" : "offline baseline only"}</span><span className="rounded-full bg-muted px-2 py-1 text-muted-foreground">{agents.length || 1} configured role(s)</span><span className="rounded-full bg-muted px-2 py-1 text-muted-foreground">{toolCount} declared tool(s)</span></div>
      </div>
    </Card>
  )
}

export function Playground() {
  const [params] = useSearchParams()
  const initialScenarioId = params.get("scenario") ?? undefined
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [traceReport, setTraceReport] = useState<Report | null>(null)
  const [exampleReport, setExampleReport] = useState<Report | null>(null)
  const [baseline, setBaseline] = useState<Report | null>(null)
  const [loading, setLoading] = useState(false)
  const [exampleLoading, setExampleLoading] = useState(false)
  const [mode, setMode] = useState(initialScenarioId ? "examples" : "trace")
  const [selectedExampleId, setSelectedExampleId] = useState<string | null>(initialScenarioId ?? null)
  const [selectedProjectId, setSelectedProjectId] = useState("")

  useEffect(() => {
    api.scenarios().then(setScenarios).catch((error) => toast.error(`Failed to load scenarios: ${error.message}`))
    api.projects().then((items) => { setProjects(items); if (items.length) setSelectedProjectId(items[0].id) }).catch(() => {})
  }, [])

  async function onAnalyze(payload: AnalyzePayload) {
    setLoading(true)
    try { setTraceReport(await api.analyze(payload)) }
    catch (error) { toast.error(`Analysis failed: ${(error as Error).message}`) }
    finally { setLoading(false) }
  }

  async function analyzeExample(id: string) {
    setSelectedExampleId(id)
    setExampleLoading(true)
    try {
      const trace = await api.example(id)
      setExampleReport(await api.analyze({ trace }))
    } catch (error) { toast.error(`Example analysis failed: ${(error as Error).message}`) }
    finally { setExampleLoading(false) }
  }

  const builtinScenarios = scenarios.filter((scenario) => scenario.source === "builtin").slice(0, 6)
  const selectedProject = projects.find((project) => project.id === selectedProjectId)

  useEffect(() => {
    if (initialScenarioId && scenarios.some((scenario) => scenario.id === initialScenarioId)) analyzeExample(initialScenarioId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scenarios, initialScenarioId])

  return (
    <div className="animate-fade-up min-w-0">
      <PageHeader title="Test lab" description="Choose what you want to test. AgentLeak tells you before every run whether it will analyze existing evidence, use sample data, or execute a model." />
      <ModeGuide />
      <Tabs value={mode} onValueChange={setMode}>
        <TabsList className="mb-5 h-auto max-w-full justify-start overflow-x-auto"><TabsTrigger value="trace"><FileJson2 className="size-3.5" /> Analyze your trace</TabsTrigger><TabsTrigger value="examples"><FlaskConical className="size-3.5" /> Explore examples</TabsTrigger><TabsTrigger value="redteam"><Shield className="size-3.5 text-sev-l4" /> Red-team a model</TabsTrigger></TabsList>

        <TabsContent value="trace" className="mt-0">
          <Card className="mb-5 border-primary/20 bg-primary/[0.035]"><div className="flex gap-3 p-4"><Info className="mt-0.5 size-4 shrink-0 text-primary" /><div><p className="text-sm font-semibold">This analyzes evidence from your agent. It does not execute it.</p><p className="mt-1 text-xs leading-relaxed text-muted-foreground">Paste or import a trace captured with AgentLeak, a framework adapter, or OpenTelemetry. Detection runs against that exact execution only.</p></div></div></Card>
          <div className="grid min-w-0 gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
            <Card className="min-w-0 lg:sticky lg:top-6 lg:h-[calc(100vh-7rem)] lg:overflow-hidden"><ConfigPanel scenarios={[]} loading={loading} onAnalyze={onAnalyze} /></Card>
            <div className="min-w-0">
              {traceReport ? <><div className="mb-3 flex flex-wrap items-center justify-between gap-2"><p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">Your trace · evaluation result</p>{!baseline && <Button variant="outline" size="sm" onClick={() => setBaseline(traceReport)}><Baseline className="size-3.5" /> Pin as baseline</Button>}</div>{baseline && <ComparisonBar baseline={baseline} current={traceReport} onClear={() => setBaseline(null)} />}<ResultsView report={traceReport} /></> : (
                <div className="space-y-5">
                  <div className="flex min-h-[220px] flex-col items-center justify-center rounded-lg border border-dashed border-border p-8 text-center"><div className="mb-3 flex size-14 items-center justify-center rounded-xl border border-border bg-card"><AgentLeakMark className={loading ? "agentleak-mark-loading !h-8 !w-7" : "!h-8 !w-7"} label="" /></div><p className="text-sm font-medium">Add one captured agent trace</p><p className="mt-1 max-w-md text-xs leading-relaxed text-muted-foreground">{loading ? "AgentLeak is evaluating the recorded execution…" : "The result will describe only the events present in this JSON. It will not make a model call or contact your agent."}</p></div>
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="examples" className="mt-0">
          <Card className="mb-5 border-sev-ok/20 bg-sev-ok/[0.035]"><div className="flex gap-3 p-4"><CheckCircle2 className="mt-0.5 size-4 shrink-0 text-sev-ok" /><div><p className="text-sm font-semibold">Safe product tour — packaged sample data only</p><p className="mt-1 text-xs leading-relaxed text-muted-foreground">These examples are prerecorded traces with fictional sensitive data and an expected clean or leaking outcome. Selecting one does not run a model or test your application.</p></div></div></Card>
          <div className="grid min-w-0 gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
            <div><p className="mb-3 text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">Choose a prerecorded trace</p><div className="grid gap-2.5">{builtinScenarios.map((scenario) => <QuickScenarioCard key={scenario.id} scenario={scenario} active={selectedExampleId === scenario.id} onSelect={analyzeExample} />)}</div></div>
            <div className="min-w-0">{exampleReport ? <><div className="mb-3 flex flex-wrap items-center justify-between gap-2"><p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">Sample trace · evaluation result</p><span className="rounded-full bg-muted px-2.5 py-1 text-[10px] text-muted-foreground">No agent executed</span></div><ResultsView report={exampleReport} /></> : <div className="flex min-h-[280px] flex-col items-center justify-center rounded-lg border border-dashed border-border p-8 text-center"><FlaskConical className="mb-3 size-7 text-muted-foreground" /><p className="text-sm font-medium">Select an example to inspect its report</p><p className="mt-1 max-w-md text-xs text-muted-foreground">Use this path to learn the product. Use “Analyze your trace” when you want evidence about your own agent.</p>{exampleLoading && <p className="mt-3 text-xs text-primary">Loading sample trace…</p>}</div>}</div>
          </div>
        </TabsContent>

        <TabsContent value="redteam" className="mt-0 min-w-0">
          <Card className="mb-5 border-sev-l4/20 bg-sev-l4/[0.025]"><div className="flex gap-3 p-4"><Zap className="mt-0.5 size-4 shrink-0 text-sev-l4" /><div><p className="text-sm font-semibold">This generates new adversarial executions</p><p className="mt-1 text-xs leading-relaxed text-muted-foreground">Offline baseline checks AgentLeak's detector coverage. Live harness sends probes to the configured OpenAI-compatible model inside AgentLeak's controlled tool environment; it does not call an arbitrary deployed application.</p></div></div></Card>
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3 rounded-lg border border-border bg-card p-4"><div className="min-w-[240px] flex-1"><label className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Test configuration</label>{projects.length ? <select value={selectedProjectId} onChange={(event) => setSelectedProjectId(event.target.value)} className="mt-2 w-full max-w-lg rounded-md border border-border bg-background px-3 py-2 text-sm">{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select> : <p className="mt-2 text-sm text-muted-foreground">Create a project to define the model, tools, purpose and evidence boundary used by the harness.</p>}</div><Button asChild variant="outline"><Link to={selectedProject ? `/projects/${selectedProject.id}` : "/projects"}>{selectedProject ? "Review test settings" : "Create test project"}<ArrowRight className="size-3.5" /></Link></Button></div>
          {selectedProject ? <><TargetReadiness project={selectedProject} /><RedTeamView projectId={selectedProject.id} /></> : <div className="grid min-h-[320px] place-items-center rounded-lg border border-dashed"><div className="text-center"><AgentLeakMark className="mx-auto !h-10 !w-8" label="" /><p className="mt-4 text-sm text-muted-foreground">No target project is available yet.</p></div></div>}
        </TabsContent>
      </Tabs>
    </div>
  )
}
