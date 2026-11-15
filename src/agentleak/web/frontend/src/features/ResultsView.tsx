// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useState, type ReactNode } from "react"
import { useSearchParams } from "react-router-dom"
import { Check, Copy, Download, TriangleAlert } from "lucide-react"
import { toast } from "sonner"
import { api, type RemediationHint, type Report, type TraceDoc } from "@/lib/api"
import { download } from "@/lib/format"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { DetectionBadge } from "./Chips"
import { ComplianceView } from "./ComplianceView"
import { FindingsTable, type TriageBinding } from "./FindingsTable"
import { FlowView } from "./FlowView"
import { ChannelVerdicts, ScorePanel } from "./ResultSummary"
import { TraceExplorer } from "./TraceExplorer"
import { TriagedScore } from "./Triage"

const TABS = ["findings", "trace", "paths", "remediation", "compliance"] as const
type Tab = (typeof TABS)[number]

function Count({ n }: { n: number }) {
  return <span className="ml-1 rounded bg-muted px-1.5 py-px font-mono text-[10px] tnum text-muted-foreground">{n}</span>
}

function RemediationBlock({ hint }: { hint: RemediationHint }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="border-b border-border px-4 py-4 last:border-b-0">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-[13px]">
        <span className="rounded border border-border px-1.5 py-0.5 text-[11px] font-medium">{hint.priority}</span>
        <code className="font-mono">{hint.channel}</code>
        <span className="text-muted-foreground">{hint.data_types.join(", ")}</span>
      </div>
      <p className="mb-2 text-[13px] text-muted-foreground">{hint.advice}</p>
      <div className="relative">
        <pre className="overflow-x-auto rounded-md border border-border bg-muted/50 p-3 pr-10 font-mono text-[12px] leading-relaxed">
          <code>{hint.code_fix}</code>
        </pre>
        <button
          type="button"
          onClick={() =>
            navigator.clipboard.writeText(hint.code_fix).then(() => {
              setCopied(true)
              window.setTimeout(() => setCopied(false), 1500)
            })
          }
          className="absolute right-2 top-2 rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label="Copy code"
        >
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
        </button>
      </div>
    </div>
  )
}

export function ResultsView({
  report,
  trace = null,
  runId,
  actions,
  onTrace,
  triage,
}: {
  report: Report
  /** The analysed trace, when the browser has it (unsaved analyses). */
  trace?: TraceDoc | null
  /** Stored run id; enables permalinks. */
  runId?: string
  actions?: ReactNode
  onTrace?: (trace: TraceDoc) => void
  /** Triage of a stored run. */
  triage?: TriageBinding
}) {
  const [params, setParams] = useSearchParams()
  const tab: Tab = (TABS as readonly string[]).includes(params.get("tab") ?? "") ? (params.get("tab") as Tab) : "findings"
  const finding = params.get("finding")
  const event = params.get("event")

  function update(next: Record<string, string | null>, push = false) {
    setParams(
      (prev) => {
        const p = new URLSearchParams(prev)
        for (const [k, v] of Object.entries(next)) {
          if (v === null) p.delete(k)
          else p.set(k, v)
        }
        return p
      },
      { replace: !push },
    )
  }

  const showEvent = (id: string | null) => update({ tab: "trace", event: id }, tab !== "trace")
  const showFinding = (id: string) => update({ tab: "findings", finding: id }, true)

  async function onExport(fmt: "json" | "html" | "markdown") {
    const ext = fmt === "markdown" ? "md" : fmt
    const name = `${runId ?? report.run_id}.${ext}`
    try {
      if (fmt === "json") download(name, JSON.stringify(report, null, 2), "application/json")
      else download(name, await api.render(fmt, report), fmt === "html" ? "text/html" : "text/markdown")
      toast.success(`Exported ${name}`)
    } catch (e) {
      toast.error(`Export failed: ${(e as Error).message}`)
    }
  }

  const atRisk = report.compliance?.summary.controls_at_risk ?? 0
  const hints = report.remediation_hints ?? []
  const paths = report.leak_paths ?? []
  const generated = new Date(report.generated_at)

  return (
    <div className="min-w-0 space-y-5">
      {/* identity */}
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between md:gap-6">
        <div className="min-w-0 md:flex-1">
          <h2 className="break-all font-mono text-base font-medium">{report.agent_name || "agent"}</h2>
          <dl className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-muted-foreground">
            <div className="flex gap-1">
              <dt>trace</dt>
              <dd className="break-all font-mono text-foreground">{report.run_id}</dd>
            </div>
            {report.scenario_id && (
              <div className="flex gap-1">
                <dt>scenario</dt>
                <dd className="break-all font-mono text-foreground">{report.scenario_id}</dd>
              </div>
            )}
            <div className="flex gap-1">
              <dt>events</dt>
              <dd className="font-mono tnum text-foreground">{report.event_count}</dd>
            </div>
            {!Number.isNaN(generated.getTime()) && (
              <div className="flex gap-1">
                <dt>analysed</dt>
                <dd className="text-foreground">
                  <time dateTime={report.generated_at}>{generated.toLocaleString()}</time>
                </dd>
              </div>
            )}
          </dl>
          <div className="mt-2">
            <DetectionBadge detection={report.detection} />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {actions}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Download /> Report
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={() => onExport("json")}>JSON (machine-readable)</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onExport("markdown")}>Markdown</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onExport("html")}>HTML, self-contained</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {(report.warnings?.length ?? 0) > 0 && (
        <div role="note" className="flex gap-2 rounded-md border border-sev-l2/40 px-3 py-2 text-[13px]">
          <TriangleAlert className="mt-0.5 size-4 shrink-0 text-sev-l2" aria-hidden />
          <ul className="space-y-1">
            {report.warnings!.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* verdict first: per channel, then the score */}
      <div className="grid min-w-0 gap-6 rounded-lg border border-border bg-card p-4 sm:p-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <ChannelVerdicts report={report} trace={trace} onSelectChannel={(c) => update({ tab: "trace", event: null, channel: c }, true)} />
        <div className="min-w-0 border-t border-border pt-5 xl:border-l xl:border-t-0 xl:pl-6 xl:pt-0">
          <ScorePanel report={report} />
          {triage?.view && report.findings.length > 0 && <TriagedScore view={triage.view} />}
        </div>
      </div>

      <Tabs value={tab} onValueChange={(v) => update({ tab: v }, true)}>
        <div className="overflow-x-auto">
          <TabsList className="h-auto justify-start">
            <TabsTrigger value="findings">
              Findings <Count n={report.findings.length} />
            </TabsTrigger>
            <TabsTrigger value="trace">
              Trace <Count n={report.event_count} />
            </TabsTrigger>
            <TabsTrigger value="paths">
              Leak paths <Count n={paths.length} />
            </TabsTrigger>
            <TabsTrigger value="remediation">
              Remediation <Count n={report.recommendations.length + hints.length} />
            </TabsTrigger>
            {report.compliance && (
              <TabsTrigger value="compliance">
                Compliance <Count n={atRisk} />
              </TabsTrigger>
            )}
          </TabsList>
        </div>

        <TabsContent value="findings" className="rounded-lg border border-border bg-card">
          <FindingsTable
            report={report}
            runId={runId}
            activeFinding={finding}
            onActivate={(id) => update({ finding: id })}
            onShowEvent={(id) => showEvent(id)}
            triage={triage}
          />
        </TabsContent>

        <TabsContent value="trace" className="rounded-lg border border-border bg-card">
          <TraceExplorer
            key={params.get("channel") ?? ""}
            report={report}
            trace={trace}
            onTrace={onTrace}
            focusEvent={event}
            onFocusEvent={(id) => update({ event: id })}
            onShowFinding={showFinding}
            initialChannel={params.get("channel")}
          />
        </TabsContent>

        <TabsContent value="paths">
          <FlowView report={report} />
        </TabsContent>

        <TabsContent value="remediation" className="rounded-lg border border-border bg-card">
          {report.recommendations.length === 0 && hints.length === 0 ? (
            <p className="px-4 py-10 text-center text-sm text-muted-foreground">Nothing to remediate: no finding was reported.</p>
          ) : (
            <>
              {report.recommendations.length > 0 && (
                <ol className="list-decimal space-y-1.5 border-b border-border py-4 pl-9 pr-4 text-[13px] marker:font-mono marker:text-muted-foreground">
                  {report.recommendations.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ol>
              )}
              {hints.map((h) => (
                <RemediationBlock key={h.channel} hint={h} />
              ))}
            </>
          )}
        </TabsContent>

        {report.compliance && (
          <TabsContent value="compliance">
            <ComplianceView compliance={report.compliance} />
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}

export function ResultSkeleton() {
  const bar = "rounded bg-muted motion-safe:animate-pulse"
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Loading result">
      <div className="space-y-2">
        <div className={cn(bar, "h-5 w-56")} />
        <div className={cn(bar, "h-3 w-80 max-w-full")} />
      </div>
      <div className="grid gap-6 rounded-lg border border-border p-5 xl:grid-cols-[1.5fr_1fr]">
        <div className="space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className={cn(bar, "h-7")} />
          ))}
        </div>
        <div className="space-y-3">
          <div className={cn(bar, "h-9 w-32")} />
          <div className={cn(bar, "h-5 w-48")} />
        </div>
      </div>
      <div className={cn(bar, "h-64")} />
    </div>
  )
}
