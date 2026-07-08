import { useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { Bot, BriefcaseMedical, ChevronRight, GraduationCap, Headset, ScanLine, ShieldCheck, TrendingUp, Users } from "lucide-react"
import { toast } from "sonner"
import { api, type AnalyzePayload, type Report, type Scenario } from "@/lib/api"
import { Card } from "@/components/ui/card"
import { ConfigPanel } from "@/features/ConfigPanel"
import { ResultsView } from "@/features/ResultsView"
import { PageHeader } from "@/layout/AppShell"

const SCENARIO_ICONS: Record<string, typeof Bot> = {
  healthcare: BriefcaseMedical,
  finance: TrendingUp,
  education: GraduationCap,
  hr: Users,
  customer_support: Headset,
}

function QuickScenarioCard({ scenario, onSelect }: { scenario: Scenario; onClick?: () => void; onSelect: (id: string) => void }) {
  const domain = scenario.domain ?? "general"
  const Icon = SCENARIO_ICONS[domain] ?? Bot
  return (
    <button
      onClick={() => onSelect(scenario.id)}
      className="group flex items-start gap-3 rounded-lg border border-border bg-card p-3.5 text-left transition-all hover:border-primary/40 hover:shadow-sm"
    >
      <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary">
        <Icon className="size-3.5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-1">
          <span className="text-[13px] font-medium capitalize leading-snug">{domain}</span>
          <ChevronRight className="size-3.5 shrink-0 text-muted-foreground group-hover:text-primary" />
        </div>
        {scenario.description && (
          <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">{scenario.description}</p>
        )}
      </div>
    </button>
  )
}

export function Playground() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [report, setReport] = useState<Report | null>(null)
  const [loading, setLoading] = useState(false)
  const [params] = useSearchParams()
  const initialScenarioId = params.get("scenario") ?? undefined

  useEffect(() => {
    api.scenarios().then(setScenarios).catch((e) => toast.error(`Failed to load scenarios: ${e.message}`))
  }, [])

  async function onAnalyze(payload: AnalyzePayload) {
    setLoading(true)
    try {
      setReport(await api.analyze(payload))
    } catch (e) {
      toast.error(`Analysis failed: ${(e as Error).message}`)
    } finally {
      setLoading(false)
    }
  }

  // Passed down to ConfigPanel so clicking a quick-start card loads the scenario there.
  const [triggerScenario, setTriggerScenario] = useState<string | undefined>(initialScenarioId)

  const builtinScenarios = scenarios.filter((s) => s.source === "builtin").slice(0, 6)

  return (
    <div className="animate-fade-up">
      <PageHeader title="Playground" description="Score any trace instantly — nothing is saved." />
      <div className="grid gap-5 lg:grid-cols-[360px_1fr]">
        <Card className="lg:sticky lg:top-6 lg:h-[calc(100vh-7rem)] lg:overflow-hidden">
          <ConfigPanel
            scenarios={scenarios}
            loading={loading}
            onAnalyze={onAnalyze}
            initialScenarioId={triggerScenario}
          />
        </Card>
        <div className="min-w-0">
          {report ? (
            <ResultsView report={report} />
          ) : (
            <div className="space-y-5">
              {/* quick-start scenario cards */}
              {builtinScenarios.length > 0 && (
                <div>
                  <p className="mb-3 text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                    Quick start — pick a scenario
                  </p>
                  <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                    {builtinScenarios.map((s) => (
                      <QuickScenarioCard
                        key={s.id}
                        scenario={s}
                        onSelect={(id) => setTriggerScenario(id + "?t=" + Date.now())}
                      />
                    ))}
                  </div>
                </div>
              )}

              {/* self-test integration hint */}
              <Card className="border-primary/20 bg-primary/[0.04]">
                <div className="flex gap-3 p-4">
                  <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
                  <div className="space-y-1.5">
                    <p className="text-sm font-medium">Let your agent test itself</p>
                    <p className="text-[12px] text-muted-foreground leading-relaxed">
                      Generate a project API key, then call <code className="font-mono text-primary text-[11px]">POST /api/selftest</code> from your agent.
                      AgentLeak analyses the trace, saves the run, and returns structured code fixes your agent can act on.
                    </p>
                    <pre className="mt-2 overflow-x-auto rounded border border-border bg-muted/60 p-3 font-mono text-[11px] leading-relaxed">
{`from agentleak import capture

with capture(run_id="v1") as cap:
    # ... run your agent ...
    pass

result = cap.analyze()
for hint in result.remediation_hints():
    print(f"[{hint['priority']}] {hint['channel']}")
    print(hint['code_fix'])
`}
                    </pre>
                  </div>
                </div>
              </Card>

              {/* original scanner icon */}
              <div className="flex min-h-[120px] flex-col items-center justify-center rounded-lg border border-dashed border-border p-8 text-center">
                <div className="relative mb-3 flex size-12 items-center justify-center overflow-hidden rounded-xl border border-border bg-card">
                  <ScanLine className="size-5 text-primary" />
                  <div className="pointer-events-none absolute inset-0 animate-scan bg-gradient-to-b from-transparent via-primary/20 to-transparent" />
                </div>
                <p className="max-w-xs text-sm text-muted-foreground">
                  Pick a scenario above or paste a trace in the left panel, then click <strong className="text-foreground">Analyze</strong>.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
