import { useMemo, useState, type ReactNode } from "react"
import { ArrowRight, Check, Code2, Copy, Download, FileJson, FileText, Lightbulb, ListChecks, ScrollText, Search, ShieldAlert, ShieldCheck, Workflow, X } from "lucide-react"
import { toast } from "sonner"
import { api, type Finding, type RemediationHint, type Report } from "@/lib/api"
import { badgeChipClass, badgeColor, download, keyInsight, LEVEL_META } from "@/lib/format"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { ComplianceView } from "./ComplianceView"
import { FlowView } from "./FlowView"
import { RiGauge } from "./RiGauge"

const PRIORITY_COLOR: Record<string, string> = {
  critical: "text-sev-l4 border-sev-l4/30 bg-sev-l4/5",
  high: "text-sev-l3 border-sev-l3/30 bg-sev-l3/5",
  medium: "text-sev-l2 border-sev-l2/30 bg-sev-l2/5",
}

function RemediationCard({ hint }: { hint: RemediationHint }) {
  const [copied, setCopied] = useState(false)

  function copyCode() {
    navigator.clipboard.writeText(hint.code_fix).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    })
  }

  const borderCls = PRIORITY_COLOR[hint.priority] ?? PRIORITY_COLOR.medium

  return (
    <Card className={`border ${borderCls.split(" ")[1]}`}>
      <div className="px-5 py-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className={`rounded px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${borderCls}`}>
            {hint.priority}
          </span>
          <code className="font-mono text-sm">{hint.channel}</code>
          <span className="text-[11px] text-muted-foreground">
            · leaks: {hint.data_types.join(", ")}
          </span>
        </div>
        <p className="mb-3 text-sm text-muted-foreground">{hint.advice}</p>
        <div className="relative">
          <pre className="overflow-x-auto rounded-md border border-border bg-muted/60 p-4 font-mono text-[12px] leading-relaxed">
            <code>{hint.code_fix}</code>
          </pre>
          <button
            onClick={copyCode}
            className="absolute right-2 top-2 rounded p-1.5 text-muted-foreground transition-colors hover:bg-border hover:text-foreground"
            title="Copy code"
          >
            {copied ? <Check className="size-3.5 text-sev-ok" /> : <Copy className="size-3.5" />}
          </button>
        </div>
      </div>
    </Card>
  )
}

function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {  return (
    <div className="rounded-md bg-muted/50 px-3.5 py-2.5">
      <div className="text-[11px] font-medium tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-1 font-mono text-lg tnum leading-none">{value}</div>
      {hint && <div className="mt-1 text-[11px] text-muted-foreground">{hint}</div>}
    </div>
  )
}

function TabCount({ n, tone }: { n: number; tone?: "danger" | "muted" }) {
  const cls =
    tone === "danger" && n > 0
      ? "bg-sev-l4/15 text-sev-l4"
      : "bg-muted text-muted-foreground"
  return <span className={`ml-1 rounded px-1.5 py-0.5 text-[10px] tnum ${cls}`}>{n}</span>
}

const LEVEL_NUM: Record<string, number> = { L4: 4, L3: 3, L2: 2, L1: 1 }

function FindingRow({ f }: { f: Finding }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <tr
        className="cursor-pointer border-t border-border transition-colors hover:bg-muted/40"
        onClick={() => setOpen((o) => !o)}
      >
        <td className="px-5 py-2.5">
          <span className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${badgeChipClass(f.badge)}`}>
            {f.level_label}
          </span>
        </td>
        <td className="px-3 py-2.5">
          <code className="font-mono text-[12px] text-muted-foreground">{f.channel}</code>
        </td>
        <td className="px-3 py-2.5">{f.data_type}</td>
        <td className="px-3 py-2.5">
          <code className="font-mono text-[12px]">{f.redacted_value || f.matched_value}</code>
        </td>
        <td className="hidden px-3 py-2.5 text-[12px] text-muted-foreground sm:table-cell">
          <span className="inline-flex items-center gap-1">
            <span className="truncate">{f.source}</span>
            <ArrowRight className="size-3 shrink-0 opacity-50" />
            <span className="truncate">{f.target}</span>
          </span>
        </td>
        <td className="px-5 py-2.5 text-[12px] text-muted-foreground">{f.detector}</td>
      </tr>
      {open && (
        <tr className="bg-muted/30">
          <td colSpan={6} className="px-5 pb-3 pt-1">
            <div className="flex gap-2 text-[12px] text-muted-foreground">
              <Lightbulb className="mt-0.5 size-3.5 shrink-0 text-primary" />
              <span>{f.recommendation}</span>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function FindingsPanel({ report }: { report: Report }) {
  const [q, setQ] = useState("")
  const [levels, setLevels] = useState<Set<number>>(new Set())
  const [channel, setChannel] = useState("all")
  const [detector, setDetector] = useState("all")

  const channels = useMemo(
    () => Array.from(new Set(report.findings.map((f) => f.channel))).sort(),
    [report.findings]
  )
  const detectors = useMemo(
    () => Array.from(new Set(report.findings.map((f) => f.detector))).sort(),
    [report.findings]
  )
  const levelCounts = useMemo(() => {
    const m: Record<number, number> = {}
    report.findings.forEach((f) => {
      m[f.level] = (m[f.level] ?? 0) + 1
    })
    return m
  }, [report.findings])

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return report.findings
      .filter((f) => {
        if (levels.size && !levels.has(f.level)) return false
        if (channel !== "all" && f.channel !== channel) return false
        if (detector !== "all" && f.detector !== detector) return false
        if (needle) {
          const hay =
            `${f.data_type} ${f.channel} ${f.detector} ${f.redacted_value} ${f.matched_value ?? ""} ${f.source} ${f.target}`.toLowerCase()
          if (!hay.includes(needle)) return false
        }
        return true
      })
      .sort((a, b) => b.level - a.level)
  }, [report.findings, q, levels, channel, detector])

  const active = levels.size > 0 || channel !== "all" || detector !== "all" || q.trim() !== ""

  function toggleLevel(l: number) {
    setLevels((s) => {
      const n = new Set(s)
      if (n.has(l)) n.delete(l)
      else n.add(l)
      return n
    })
  }
  function clearAll() {
    setQ("")
    setLevels(new Set())
    setChannel("all")
    setDetector("all")
  }

  if (report.findings.length === 0) {
    return (
      <Card>
        <div className="px-5 py-12 text-center text-sm text-muted-foreground">No leaks detected. 🎉</div>
      </Card>
    )
  }

  return (
    <Card>
      {/* filter toolbar */}
      <div className="space-y-3 border-b border-border px-5 py-3.5">
        <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search type, value, channel, source…"
              className="h-9 pl-9"
            />
          </div>
          <Select value={channel} onValueChange={setChannel}>
            <SelectTrigger className="h-9 w-full sm:w-[180px]">
              <SelectValue placeholder="Channel" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All channels</SelectItem>
              {channels.map((c) => (
                <SelectItem key={c} value={c}>
                  {c}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={detector} onValueChange={setDetector}>
            <SelectTrigger className="h-9 w-full sm:w-[150px]">
              <SelectValue placeholder="Detector" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All detectors</SelectItem>
              {detectors.map((d) => (
                <SelectItem key={d} value={d}>
                  {d}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {LEVEL_META.map((l) => {
            const num = LEVEL_NUM[l.label]
            const n = levelCounts[num] ?? 0
            const on = levels.has(num)
            return (
              <button
                key={l.label}
                disabled={n === 0}
                onClick={() => toggleLevel(num)}
                className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors disabled:opacity-40 ${
                  on ? badgeChipClass(l.badge) : "border-border text-muted-foreground hover:text-foreground"
                }`}
                title={l.name}
              >
                {l.label}
                <span className="ml-1 tnum opacity-70">{n}</span>
              </button>
            )
          })}
          <span className="ml-auto text-[11px] tnum text-muted-foreground">
            {filtered.length} of {report.findings.length}
          </span>
          {active && (
            <button
              onClick={clearAll}
              className="inline-flex items-center gap-1 rounded px-1.5 py-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
            >
              <X className="size-3" /> Clear
            </button>
          )}
        </div>
      </div>

      <ScrollArea className="max-h-[520px]">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-card">
            <tr className="text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <th className="px-5 py-2 font-medium">Level</th>
              <th className="px-3 py-2 font-medium">Channel</th>
              <th className="px-3 py-2 font-medium">Type</th>
              <th className="px-3 py-2 font-medium">Value</th>
              <th className="hidden px-3 py-2 font-medium sm:table-cell">Path</th>
              <th className="px-5 py-2 font-medium">Detector</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-5 py-10 text-center text-muted-foreground">
                  No findings match your filters.
                </td>
              </tr>
            ) : (
              filtered.map((f) => <FindingRow key={f.finding_id} f={f} />)
            )}
          </tbody>
        </table>
      </ScrollArea>
    </Card>
  )
}

export function ResultsView({ report }: { report: Report }) {
  const insight = keyInsight(report)
  const maxRi = Math.max(...report.channel_risks.map((c) => c.ri), 0.0001)
  const atRisk = report.compliance?.summary.controls_at_risk ?? 0
  const leakPaths = report.leak_paths?.length ?? 0
  const hasFlow = (report.flow?.nodes.length ?? 0) > 0

  async function onExport(fmt: "json" | "html" | "markdown") {
    try {
      if (fmt === "json") {
        download(`${report.run_id}.json`, JSON.stringify(report, null, 2), "application/json")
      } else {
        const text = await api.render(fmt, report)
        const ext = fmt === "markdown" ? "md" : "html"
        download(`${report.run_id}.${ext}`, text, fmt === "html" ? "text/html" : "text/markdown")
      }
      toast.success(`Exported ${report.run_id}.${fmt === "markdown" ? "md" : fmt}`)
    } catch (e) {
      toast.error(`Export failed: ${(e as Error).message}`)
    }
  }

  return (
    <div className="animate-fade-up space-y-5">
      {/* header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate font-mono text-sm">{report.agent_name}</div>
          <div className="text-xs text-muted-foreground">
            run <span className="text-foreground">{report.run_id}</span> · {report.event_count} events
            {report.scenario_id ? <> · {report.scenario_id}</> : null}
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <Button variant="outline" size="sm" onClick={() => onExport("json")}>
            <FileJson /> JSON
          </Button>
          <Button variant="outline" size="sm" onClick={() => onExport("markdown")}>
            <FileText /> MD
          </Button>
          <Button variant="outline" size="sm" onClick={() => onExport("html")}>
            <Download /> HTML
          </Button>
        </div>
      </div>

      {/* hero: gauge + headline stats (always visible) */}
      <Card className="overflow-hidden">
        <div className="grid gap-6 p-5 md:grid-cols-[260px_1fr]">
          <div className="flex items-center justify-center border-b border-border pb-4 md:border-b-0 md:border-r md:pb-0 md:pr-6">
            <RiGauge report={report} />
          </div>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
              <Stat label="WSL" value={report.wsl} hint="weighted leakage" />
              <Stat label="ρ_S" value={report.rho_s} hint="vault density" />
              <Stat
                label="Leaked"
                value={`${report.summary.leaked_secrets}/${report.summary.vault_secrets}`}
                hint="secrets in scope"
              />
              <Stat label="Findings" value={report.summary.total_findings} hint="disclosures" />
            </div>
            <div>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-x-3">
                <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                  Leaked by severity level
                </span>
                <span className="text-[11px] text-muted-foreground">{report.scope_def}</span>
              </div>
              <div className="grid grid-cols-4 gap-2">
                {LEVEL_META.map((l) => {
                  const n = report.summary.level_profile[l.label as "L4"] ?? 0
                  const vault = report.summary.vault_level_profile[l.label as "L4"] ?? 0
                  return (
                    <Tooltip key={l.label}>
                      <TooltipTrigger asChild>
                        <div className="rounded-md border border-border bg-card px-3 py-2">
                          <div className="font-mono text-xl tnum leading-none" style={{ color: badgeColor(l.badge) }}>
                            {n}
                          </div>
                          <div className="mt-1 flex items-center justify-between text-[11px] text-muted-foreground">
                            <span>{l.label}</span>
                            <span className="tnum">/{vault}</span>
                          </div>
                        </div>
                      </TooltipTrigger>
                      <TooltipContent>
                        {l.name} — {n} leaked of {vault} in scope
                      </TooltipContent>
                    </Tooltip>
                  )
                })}
              </div>
            </div>
            {report.blocked && (
              <div className="flex items-center gap-2 rounded-md border border-sev-l4/30 bg-sev-l4/10 px-3 py-2 text-sm text-sev-l4">
                <ShieldAlert className="size-4 shrink-0" />
                Blocked — this run would fail a CI privacy gate.
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* detail tabs */}
      <Tabs defaultValue="overview">
        <TabsList className="flex h-auto w-full flex-wrap justify-start">
          <TabsTrigger value="overview">
            <ScrollText className="size-3.5" /> Overview
          </TabsTrigger>
          {hasFlow && (
            <TabsTrigger value="flow">
              <Workflow className="size-3.5" /> Leak flow
              <TabCount n={leakPaths} tone="danger" />
            </TabsTrigger>
          )}
          <TabsTrigger value="findings">
            <ListChecks className="size-3.5" /> Findings
            <TabCount n={report.findings.length} tone="danger" />
          </TabsTrigger>
          <TabsTrigger value="recommendations">
            <Lightbulb className="size-3.5" /> Recommendations
            <TabCount n={report.recommendations.length} tone="muted" />
          </TabsTrigger>
          {(report.remediation_hints?.length ?? 0) > 0 && (
            <TabsTrigger value="codefixes">
              <Code2 className="size-3.5" /> Code fixes
              <TabCount n={report.remediation_hints!.length} tone="danger" />
            </TabsTrigger>
          )}
          {report.compliance && (
            <TabsTrigger value="compliance">
              {atRisk > 0 ? <ShieldAlert className="size-3.5" /> : <ShieldCheck className="size-3.5" />} Compliance
              <TabCount n={atRisk} tone="danger" />
            </TabsTrigger>
          )}
        </TabsList>

        {/* Overview: key insight + risk by channel */}
        <TabsContent value="overview" className="space-y-5">
          {insight && (
            <Card className="border-primary/30 bg-primary/[0.06]">
              <div className="flex gap-3 p-4">
                <Lightbulb className="mt-0.5 size-4 shrink-0 text-primary" />
                <p className="text-sm leading-relaxed">
                  <span className="font-semibold text-primary">Key insight. </span>
                  {insight}
                </p>
              </div>
            </Card>
          )}
          <Card>
            <div className="border-b border-border px-5 py-3">
              <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                Risk by channel
              </span>
            </div>
            <div className="divide-y divide-border">
              {report.channel_risks.length === 0 && (
                <div className="px-5 py-6 text-sm text-muted-foreground">No leaks detected in any channel.</div>
              )}
              {report.channel_risks.map((c) => (
                <div key={c.channel} className="grid grid-cols-[1fr_auto] items-center gap-4 px-5 py-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2.5">
                      <span className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${badgeChipClass(c.level)}`}>
                        {c.level_label}
                      </span>
                      <code className="truncate font-mono text-[13px]">{c.channel}</code>
                      <span className="text-[11px] text-muted-foreground">{c.finding_count} finding(s)</span>
                    </div>
                    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        key={`${report.run_id}-${c.channel}`}
                        className="bar-grow h-full rounded-full"
                        style={{ width: `${(c.ri / maxRi) * 100}%`, backgroundColor: badgeColor(c.level) }}
                      />
                    </div>
                  </div>
                  <div className="font-mono text-sm tnum text-muted-foreground">{c.ri.toFixed(3)}</div>
                </div>
              ))}
            </div>
          </Card>
        </TabsContent>

        {/* Leak flow — topology + propagation paths */}
        {hasFlow && (
          <TabsContent value="flow">
            <FlowView report={report} />
          </TabsContent>
        )}

        {/* Findings */}
        <TabsContent value="findings">
          <FindingsPanel report={report} />
        </TabsContent>

        {/* Recommendations */}
        <TabsContent value="recommendations">
          <Card>
            <div className="border-b border-border px-5 py-3">
              <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                Recommendations
              </span>
            </div>
            {report.recommendations.length === 0 ? (
              <div className="px-5 py-10 text-center text-sm text-muted-foreground">
                No recommendations — nothing leaked.
              </div>
            ) : (
              <ul className="divide-y divide-border">
                {report.recommendations.map((r, i) => (
                  <li key={i} className="flex gap-2.5 px-5 py-3 text-sm">
                    <span className="select-none font-mono text-primary">→</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            )}
            {(report.remediation_hints?.length ?? 0) > 0 && (
              <div className="border-t border-border px-5 py-3">
                <p className="text-[11px] text-muted-foreground">
                  See the <strong className="text-foreground">Code fixes</strong> tab for copy-paste patches per leaked channel.
                </p>
              </div>
            )}
          </Card>
        </TabsContent>

        {/* Code fixes */}
        {(report.remediation_hints?.length ?? 0) > 0 && (
          <TabsContent value="codefixes" className="space-y-4">
            {report.remediation_hints!.map((hint) => (
              <RemediationCard key={hint.channel} hint={hint} />
            ))}
          </TabsContent>
        )}

        {/* Compliance */}
        {report.compliance && (
          <TabsContent value="compliance">
            <ComplianceView compliance={report.compliance} />
          </TabsContent>
        )}
      </Tabs>
    </div>
  )
}
