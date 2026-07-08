import { useEffect, useMemo, useState } from "react"
import { ArrowDown, ArrowRight, ArrowUp, GitCompare, Minus, Trophy } from "lucide-react"
import { toast } from "sonner"
import {
  api,
  type Progression,
  type RunComparison,
  type RunHistoryEntry,
} from "@/lib/api"
import { scoreColor } from "@/lib/format"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

/** Score progression chart + aggregate stats + run-to-run comparison. */
export function ProgressionView({ projectId }: { projectId: string }) {
  const [history, setHistory] = useState<RunHistoryEntry[]>([])
  const [prog, setProg] = useState<Progression | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    setLoading(true)
    api
      .history(projectId)
      .then((h) => {
        if (!active) return
        setHistory(h.runs)
        setProg("total_runs" in h.progression ? (h.progression as Progression) : null)
      })
      .catch(() => {})
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [projectId])

  if (loading) return <div className="text-sm text-muted-foreground">Loading history…</div>
  if (!history.length)
    return (
      <Card className="p-10 text-center text-sm text-muted-foreground">
        No runs recorded yet. Run an audit to start tracking your score progression.
      </Card>
    )

  return (
    <div className="space-y-4">
      {prog && <ProgressionStats prog={prog} />}
      <ScoreTrend runs={history} />
      <CompareRuns projectId={projectId} runs={history} />
    </div>
  )
}

// ----------------------------------------------------------- Stat cards
function ProgressionStats({ prog }: { prog: Progression }) {
  const dir =
    prog.direction === "improving"
      ? { icon: ArrowUp, color: "hsl(var(--sev-ok))", label: "Improving" }
      : prog.direction === "regressing"
        ? { icon: ArrowDown, color: "hsl(var(--sev-l4))", label: "Regressing" }
        : { icon: Minus, color: "hsl(var(--muted-foreground))", label: "Stable" }
  const Icon = dir.icon

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard label="Latest score">
        <span className="text-2xl font-semibold tnum" style={{ color: scoreColor(prog.latest_score) }}>
          {prog.latest_score}
          <span className="text-sm text-muted-foreground">/100</span>
        </span>
      </StatCard>

      <StatCard label="Trend">
        <span className="flex items-center gap-1.5 text-2xl font-semibold tnum" style={{ color: dir.color }}>
          <Icon className="size-5" />
          {prog.total_delta >= 0 ? "+" : ""}
          {prog.total_delta}
        </span>
        <span className="text-[11px] text-muted-foreground">{dir.label} over {prog.total_runs} runs</span>
      </StatCard>

      <StatCard label="Best score">
        <span className="flex items-center gap-1.5 text-2xl font-semibold tnum" style={{ color: scoreColor(prog.best_score) }}>
          <Trophy className="size-4 text-amber-400" />
          {prog.best_score}
        </span>
      </StatCard>

      <StatCard label="Blocked runs">
        <span className="text-2xl font-semibold tnum">
          {prog.blocked_runs}
          <span className="text-sm text-muted-foreground">/{prog.total_runs}</span>
        </span>
      </StatCard>
    </div>
  )
}

function StatCard({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <Card className="p-4">
      <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="flex flex-col">{children}</div>
    </Card>
  )
}

// ------------------------------------------------------- Score trend SVG
function ScoreTrend({ runs }: { runs: RunHistoryEntry[] }) {
  // runs are oldest-first already
  const W = 720
  const H = 160
  const pad = { l: 30, r: 12, t: 14, b: 24 }
  const iw = W - pad.l - pad.r
  const ih = H - pad.t - pad.b
  const n = runs.length
  const x = (i: number) => pad.l + (n <= 1 ? iw / 2 : (i / (n - 1)) * iw)
  const y = (s: number) => pad.t + (1 - Math.min(100, Math.max(0, s)) / 100) * ih
  const line = runs.map((r, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(r.privacy_score).toFixed(1)}`).join(" ")
  const area = `${line} L ${x(n - 1).toFixed(1)} ${(pad.t + ih).toFixed(1)} L ${x(0).toFixed(1)} ${(pad.t + ih).toFixed(1)} Z`

  return (
    <Card className="p-4">
      <div className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        Privacy score — progression
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="Privacy score over runs">
        <defs>
          <linearGradient id="scoreArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.18} />
            <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
          </linearGradient>
        </defs>
        {[0, 40, 70, 90, 100].map((g) => (
          <g key={g}>
            <line
              x1={pad.l}
              x2={W - pad.r}
              y1={y(g)}
              y2={y(g)}
              stroke="hsl(var(--border))"
              strokeWidth={1}
              strokeDasharray={g === 70 ? "3 3" : undefined}
            />
            <text x={pad.l - 6} y={y(g) + 3} textAnchor="end" className="fill-muted-foreground" style={{ fontSize: 9 }}>
              {g}
            </text>
          </g>
        ))}
        {n > 1 && <path d={area} fill="url(#scoreArea)" />}
        <path d={line} fill="none" stroke="hsl(var(--primary))" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {runs.map((r, i) => (
          <g key={r.id}>
            <circle cx={x(i)} cy={y(r.privacy_score)} r={3.5} fill={scoreColor(r.privacy_score)}>
              <title>
                #{r.rank} · {r.label || r.agent_name || "run"} · score {r.privacy_score}/100
              </title>
            </circle>
          </g>
        ))}
      </svg>
      <div className="mt-1 flex justify-between text-[10px] text-muted-foreground">
        <span>oldest</span>
        <span>latest</span>
      </div>
    </Card>
  )
}

// --------------------------------------------------------- Compare runs
function CompareRuns({ projectId, runs }: { projectId: string; runs: RunHistoryEntry[] }) {
  const sorted = useMemo(() => [...runs].reverse(), [runs]) // newest first for picker
  const [a, setA] = useState("")
  const [b, setB] = useState("")
  const [cmp, setCmp] = useState<RunComparison | null>(null)
  const [busy, setBusy] = useState(false)

  // Default A=oldest, B=newest for a quick before/after view.
  useEffect(() => {
    if (runs.length >= 2) {
      setA(runs[0].id)
      setB(runs[runs.length - 1].id)
    }
  }, [runs])

  async function run() {
    if (!a || !b || a === b) return toast.error("Pick two different runs")
    setBusy(true)
    try {
      setCmp(await api.compareRuns(projectId, a, b))
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (runs.length < 2) return null

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2 text-sm">
          <GitCompare className="size-4 text-muted-foreground" />
          <span className="text-muted-foreground">Compare</span>
        </div>
        <RunPicker runs={sorted} value={a} onChange={setA} placeholder="Baseline (A)" />
        <ArrowRight className="size-3.5 text-muted-foreground" />
        <RunPicker runs={sorted} value={b} onChange={setB} placeholder="Current (B)" />
        <Button size="sm" variant="outline" onClick={run} disabled={busy}>
          Compare
        </Button>
      </div>
      {cmp && <CompareResult cmp={cmp} />}
    </Card>
  )
}

function RunPicker({
  runs,
  value,
  onChange,
  placeholder,
}: {
  runs: RunHistoryEntry[]
  value: string
  onChange: (v: string) => void
  placeholder: string
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="h-8 w-56 text-xs">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {runs.map((r) => (
          <SelectItem key={r.id} value={r.id}>
            #{r.rank} · {r.label || r.agent_name || "run"} · {r.privacy_score}/100
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function CompareResult({ cmp }: { cmp: RunComparison }) {
  const { diff, run_a, run_b } = cmp
  const findingsA = run_a.report?.summary?.total_findings ?? 0
  const findingsB = run_b.report?.summary?.total_findings ?? 0

  return (
    <div className="space-y-4 p-4">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <DiffMetric label="Privacy score" a={run_a.privacy_score} b={run_b.privacy_score} delta={diff.delta_score} />
        <DiffMetric label="Risk Index" a={run_a.risk_index} b={run_b.risk_index} delta={diff.delta_ri} invert decimals={3} />
        <DiffMetric label="Findings" a={findingsA} b={findingsB} delta={diff.delta_findings} invert />
        <DiffMetric label="Leaked secrets" a={run_a.leaked_secrets} b={run_b.leaked_secrets} delta={diff.delta_leaked} invert />
      </div>

      {diff.frameworks.length > 0 && (
        <div>
          <div className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Compliance frameworks
          </div>
          <div className="flex flex-wrap gap-1.5">
            {diff.frameworks.map((fw) => {
              const color =
                fw.change === "fixed"
                  ? "text-sev-ok bg-sev-ok/12 ring-sev-ok/25"
                  : fw.change === "regressed"
                    ? "text-sev-l4 bg-sev-l4/12 ring-sev-l4/25"
                    : "text-muted-foreground bg-muted ring-border"
              return (
                <span
                  key={fw.id}
                  className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${color}`}
                  title={`${fw.before} → ${fw.after}`}
                >
                  {fw.change === "fixed" ? "✓" : fw.change === "regressed" ? "✗" : "•"} {fw.id}
                </span>
              )
            })}
          </div>
        </div>
      )}

      <div className="flex items-center gap-2 text-sm">
        {diff.score_direction === "improved" ? (
          <span className="flex items-center gap-1.5 font-medium text-sev-ok">
            <ArrowUp className="size-4" /> Improved
          </span>
        ) : diff.score_direction === "regressed" ? (
          <span className="flex items-center gap-1.5 font-medium text-sev-l4">
            <ArrowDown className="size-4" /> Regressed
          </span>
        ) : (
          <span className="flex items-center gap-1.5 font-medium text-muted-foreground">
            <Minus className="size-4" /> Unchanged
          </span>
        )}
        {diff.blocked_resolved && (
          <span className="rounded-full bg-sev-ok/12 px-2.5 py-0.5 text-xs font-medium text-sev-ok ring-1 ring-inset ring-sev-ok/25">
            Blocker resolved
          </span>
        )}
      </div>
    </div>
  )
}

function DiffMetric({
  label,
  a,
  b,
  delta,
  invert = false,
  decimals = 0,
}: {
  label: string
  a: number
  b: number
  delta: number
  invert?: boolean
  decimals?: number
}) {
  const fmt = (v: number) => (decimals ? v.toFixed(decimals) : String(v))
  const positiveIsGood = delta > 0 !== invert
  const color =
    delta === 0
      ? "text-muted-foreground"
      : positiveIsGood
        ? "text-sev-ok"
        : "text-sev-l4"
  const sign = delta > 0 ? "+" : ""
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-1 flex items-baseline gap-2 font-mono tnum text-sm">
        <span className="text-muted-foreground">{fmt(a)}</span>
        <ArrowRight className="size-3 text-muted-foreground" />
        <span className="font-semibold">{fmt(b)}</span>
        {delta !== 0 && (
          <span className={`ml-auto text-xs font-medium ${color}`}>
            {sign}
            {fmt(delta)}
          </span>
        )}
      </div>
    </div>
  )
}
