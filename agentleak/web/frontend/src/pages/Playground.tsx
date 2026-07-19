import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { ArrowRight, Baseline, Bot, BriefcaseMedical, ChevronRight, GraduationCap, Headset, RotateCcw, Shield, ShieldCheck, TrendingUp, Users } from "lucide-react"
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

function QuickScenarioCard({ scenario, onSelect }: { scenario: Scenario; onSelect: (id: string) => void }) {
  const domain = scenario.domain ?? "general"
  const Icon = SCENARIO_ICONS[domain] ?? Bot
  return (
    <button onClick={() => onSelect(scenario.id)} className="group flex min-w-0 items-start gap-3 rounded-lg border border-border bg-card p-3.5 text-left transition-all hover:border-primary/40 hover:shadow-sm">
      <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary"><Icon className="size-3.5" /></div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-1"><span className="text-[13px] font-medium capitalize leading-snug">{domain}</span><ChevronRight className="size-3.5 shrink-0 text-muted-foreground group-hover:text-primary" /></div>
        {scenario.description && <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">{scenario.description}</p>}
      </div>
    </button>
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
        <div className="min-w-0"><p className="text-sm font-semibold">Target profile · {project.name}</p><p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{project.description || "Add a purpose and limitations in project settings so probes can be interpreted against the intended boundary."}</p></div>
        <div className="flex flex-wrap gap-2 text-[10px]"><span className={`rounded-full px-2 py-1 ${hasPurpose ? "bg-sev-ok/10 text-sev-ok" : "bg-sev-l2/10 text-sev-l2"}`}>{hasPurpose ? "purpose defined" : "purpose missing"}</span><span className={`rounded-full px-2 py-1 ${hasTarget ? "bg-sev-ok/10 text-sev-ok" : "bg-muted text-muted-foreground"}`}>{hasTarget ? "live target ready" : "scripted only"}</span><span className="rounded-full bg-muted px-2 py-1 text-muted-foreground">{agents.length || 1} agent(s)</span><span className="rounded-full bg-muted px-2 py-1 text-muted-foreground">{toolCount} tool(s)</span></div>
      </div>
    </Card>
  )
}

export function Playground() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [report, setReport] = useState<Report | null>(null)
  const [baseline, setBaseline] = useState<Report | null>(null)
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState("trace")
  const [selectedProjectId, setSelectedProjectId] = useState("")
  const [params] = useSearchParams()
  const initialScenarioId = params.get("scenario") ?? undefined
  const [triggerScenario, setTriggerScenario] = useState<string | undefined>(initialScenarioId)

  useEffect(() => {
    api.scenarios().then(setScenarios).catch((error) => toast.error(`Failed to load scenarios: ${error.message}`))
    api.projects().then((items) => { setProjects(items); if (items.length) setSelectedProjectId(items[0].id) }).catch(() => {})
  }, [])

  async function onAnalyze(payload: AnalyzePayload) {
    setLoading(true)
    try { setReport(await api.analyze(payload)) }
    catch (error) { toast.error(`Analysis failed: ${(error as Error).message}`) }
    finally { setLoading(false) }
  }

  const builtinScenarios = scenarios.filter((scenario) => scenario.source === "builtin").slice(0, 6)
  const selectedProject = projects.find((project) => project.id === selectedProjectId)

  return (
    <div className="animate-fade-up min-w-0">
      <PageHeader title="Playground" description="Analyze a trace, assert a privacy contract, compare a baseline, or launch an adversarial campaign." />
      <Tabs value={mode} onValueChange={setMode}>
        <TabsList className="mb-5"><TabsTrigger value="trace">Trace evaluation</TabsTrigger><TabsTrigger value="redteam"><Shield className="size-3.5 text-sev-l4" /> Red-team lab</TabsTrigger></TabsList>

        <TabsContent value="trace" className="mt-0">
          <div className="grid min-w-0 gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
            <Card className="min-w-0 lg:sticky lg:top-6 lg:h-[calc(100vh-7rem)] lg:overflow-hidden"><ConfigPanel scenarios={scenarios} loading={loading} onAnalyze={onAnalyze} initialScenarioId={triggerScenario} /></Card>
            <div className="min-w-0">
              {report ? <><div className="mb-3 flex flex-wrap items-center justify-between gap-2"><p className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">Evaluation result</p>{!baseline && <Button variant="outline" size="sm" onClick={() => setBaseline(report)}><Baseline className="size-3.5" /> Set as baseline</Button>}</div>{baseline && <ComparisonBar baseline={baseline} current={report} onClear={() => setBaseline(null)} />}<ResultsView report={report} /></> : (
                <div className="space-y-5">
                  {builtinScenarios.length > 0 && <div><p className="mb-3 text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">Quick start — pick a scenario</p><div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">{builtinScenarios.map((scenario) => <QuickScenarioCard key={scenario.id} scenario={scenario} onSelect={(id) => setTriggerScenario(`${id}?t=${Date.now()}`)} />)}</div></div>}
                  <Card className="border-primary/20 bg-primary/[0.04]"><div className="flex gap-3 p-4"><ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" /><div className="min-w-0 space-y-1.5"><p className="text-sm font-medium">Assertions, not manual review only</p><p className="text-[12px] leading-relaxed text-muted-foreground">Enable the evaluation gate to enforce a maximum Risk Index, leaked-finding budget, forbidden L4 data and explicit vault scope. Pin any result as a baseline before testing a remediation.</p></div></div></Card>
                  <div className="flex min-h-[150px] flex-col items-center justify-center rounded-lg border border-dashed border-border p-8 text-center"><div className="mb-3 flex size-14 items-center justify-center rounded-xl border border-border bg-card"><AgentLeakMark className={loading ? "agentleak-mark-loading !h-8 !w-7" : "!h-8 !w-7"} label="" /></div><p className="max-w-md text-sm text-muted-foreground">{loading ? "AgentLeak is evaluating channels, canaries, assertions and leak paths…" : <>Pick a scenario, import JSON, or paste a trace in the left panel, then click <strong className="text-foreground">Analyze</strong>.</>}</p></div>
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="redteam" className="mt-0 min-w-0">
          <div className="mb-5 flex flex-wrap items-end justify-between gap-3 rounded-lg border border-border bg-card p-4"><div className="min-w-[240px] flex-1"><label className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Target project</label>{projects.length ? <select value={selectedProjectId} onChange={(event) => setSelectedProjectId(event.target.value)} className="mt-2 w-full max-w-lg rounded-md border border-border bg-background px-3 py-2 text-sm">{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select> : <p className="mt-2 text-sm text-muted-foreground">Create a project to define the target boundary and persist campaign evidence.</p>}</div><Button asChild variant="outline"><Link to={selectedProject ? `/projects/${selectedProject.id}` : "/projects"}>{selectedProject ? "Open target settings" : "Create project"}<ArrowRight className="size-3.5" /></Link></Button></div>
          {selectedProject ? <><TargetReadiness project={selectedProject} /><RedTeamView projectId={selectedProject.id} /></> : <div className="grid min-h-[320px] place-items-center rounded-lg border border-dashed"><div className="text-center"><AgentLeakMark className="mx-auto !h-10 !w-8" label="" /><p className="mt-4 text-sm text-muted-foreground">No target project is available yet.</p></div></div>}
        </TabsContent>
      </Tabs>
    </div>
  )
}
