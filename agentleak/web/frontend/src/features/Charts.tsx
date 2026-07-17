import { useMemo, useState, type MouseEvent } from "react"
import { Activity, ArrowDownRight, ArrowRight, ArrowUpRight, ShieldCheck } from "lucide-react"
import type { RunSummary } from "@/lib/api"
import { verdictColor } from "@/lib/format"
import { Card } from "@/components/ui/card"

const VERDICTS: RunSummary["verdict"][] = ["Pass", "Conditional pass", "High risk", "Fail"]

function dateLabel(timestamp: number, detailed = false) {
  return new Intl.DateTimeFormat(undefined, detailed
    ? { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }
    : { month: "short", day: "numeric" },
  ).format(new Date(timestamp * 1000))
}

function smoothPath(points: { x: number; y: number }[]) {
  if (points.length < 2) return ""
  return points.slice(1).reduce((path, point, index) => {
    const previous = points[index]
    const midpoint = (previous.x + point.x) / 2
    return `${path} C ${midpoint.toFixed(1)} ${previous.y.toFixed(1)}, ${midpoint.toFixed(1)} ${point.y.toFixed(1)}, ${point.x.toFixed(1)} ${point.y.toFixed(1)}`
  }, `M ${points[0].x.toFixed(1)} ${points[0].y.toFixed(1)}`)
}

function RiTrend({ runs }: { runs: RunSummary[] }) {
  const series = useMemo(() => [...runs].reverse(), [runs])
  const [hovered, setHovered] = useState<number | null>(null)
  const W = 720
  const H = 230
  const pad = { l: 42, r: 18, t: 18, b: 34 }
  const iw = W - pad.l - pad.r
  const ih = H - pad.t - pad.b
  const x = (i: number) => pad.l + (series.length <= 1 ? iw / 2 : (i / (series.length - 1)) * iw)
  const y = (ri: number) => pad.t + (1 - Math.min(1, Math.max(0, ri))) * ih
  const points = series.map((run, index) => ({ x: x(index), y: y(run.risk_index), run }))
  const line = smoothPath(points)
  const latestPoint = points[points.length - 1]
  const latestRun = series[series.length - 1]
  const area = line ? `${line} L ${latestPoint.x} ${H - pad.b} L ${points[0].x} ${H - pad.b} Z` : ""
  const activeIndex = hovered ?? Math.max(0, series.length - 1)
  const active = points[activeIndex]
  const delta = series.length > 1 ? latestRun.risk_index - series[0].risk_index : 0
  const DeltaIcon = delta < 0 ? ArrowDownRight : delta > 0 ? ArrowUpRight : ArrowRight

  function trackPointer(event: MouseEvent<SVGSVGElement>) {
    if (series.length < 2) return
    const rect = event.currentTarget.getBoundingClientRect()
    const svgX = ((event.clientX - rect.left) / rect.width) * W
    const ratio = Math.max(0, Math.min(1, (svgX - pad.l) / iw))
    setHovered(Math.round(ratio * (series.length - 1)))
  }

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-5 py-4">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold">
            <Activity className="size-4 text-primary" /> Risk trajectory
          </div>
          <p className="mt-1 text-xs text-muted-foreground">AgentRisk over time · lower is safer</p>
        </div>
        {series.length > 0 && (
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="font-mono text-xl font-semibold tnum">{latestRun.risk_index.toFixed(3)}</div>
              <div className="text-[10px] uppercase tracking-wide text-muted-foreground">latest RI</div>
            </div>
            {series.length > 1 && (
              <span
                className="inline-flex items-center gap-1 rounded-full px-2 py-1 font-mono text-[11px] tnum"
                style={{
                  color: delta <= 0 ? "hsl(var(--sev-ok))" : "hsl(var(--sev-l4))",
                  background: delta <= 0 ? "hsl(var(--sev-ok) / .1)" : "hsl(var(--sev-l4) / .1)",
                }}
              >
                <DeltaIcon className="size-3" /> {delta > 0 ? "+" : ""}{delta.toFixed(3)}
              </span>
            )}
          </div>
        )}
      </div>
      {series.length === 0 ? (
        <div className="flex h-[230px] items-center justify-center text-xs text-muted-foreground">No runs yet</div>
      ) : (
        <div className="relative px-3 pb-2 pt-1">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="w-full touch-none"
            role="img"
            aria-label="Interactive Risk Index trajectory"
            onMouseMove={trackPointer}
            onMouseLeave={() => setHovered(null)}
          >
            <defs>
              <linearGradient id="risk-area" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity="0.2" />
                <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity="0" />
              </linearGradient>
              <filter id="risk-glow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            </defs>

            {[
              { from: 0.75, to: 1, color: "hsl(var(--sev-l4) / .035)" },
              { from: 0.5, to: 0.75, color: "hsl(var(--sev-l3) / .03)" },
              { from: 0.25, to: 0.5, color: "hsl(var(--sev-l2) / .025)" },
              { from: 0, to: 0.25, color: "hsl(var(--sev-ok) / .025)" },
            ].map((band) => (
              <rect key={band.from} x={pad.l} y={y(band.to)} width={iw} height={y(band.from) - y(band.to)} fill={band.color} />
            ))}
            {[0, 0.25, 0.5, 0.75, 1].map((grid) => (
              <g key={grid}>
                <line x1={pad.l} x2={W - pad.r} y1={y(grid)} y2={y(grid)} stroke="hsl(var(--border))" strokeWidth={1} strokeDasharray={grid === 0 || grid === 1 ? "0" : "4 5"} />
                <text x={pad.l - 9} y={y(grid) + 3} textAnchor="end" className="fill-muted-foreground" style={{ fontSize: 9 }}>
                  {grid.toFixed(2)}
                </text>
              </g>
            ))}

            {area && <path d={area} fill="url(#risk-area)" />}
            {line && <path d={line} fill="none" stroke="hsl(var(--primary))" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />}

            {points.map((point, index) => (
              <g key={point.run.id}>
                <circle cx={point.x} cy={point.y} r={index === activeIndex ? 7 : 5} fill="hsl(var(--card))" stroke={verdictColor(point.run.verdict)} strokeWidth={2.5} className="transition-all" />
                <circle cx={point.x} cy={point.y} r={2.2} fill={verdictColor(point.run.verdict)} />
              </g>
            ))}

            {active && (
              <g pointerEvents="none">
                <line x1={active.x} x2={active.x} y1={pad.t} y2={H - pad.b} stroke="hsl(var(--foreground) / .18)" strokeDasharray="3 4" />
                <g transform={`translate(${Math.max(pad.l, Math.min(W - 170, active.x - 70))},${Math.max(6, active.y - 62)})`}>
                  <rect width="146" height="48" rx="8" fill="hsl(var(--popover))" stroke="hsl(var(--border))" />
                  <text x="11" y="17" className="fill-muted-foreground" style={{ fontSize: 9 }}>{dateLabel(active.run.created_at, true)}</text>
                  <text x="11" y="35" className="fill-foreground" style={{ fontSize: 12, fontWeight: 600 }}>RI {active.run.risk_index.toFixed(3)}</text>
                  <circle cx="130" cy="31" r="4" fill={verdictColor(active.run.verdict)} filter="url(#risk-glow)" />
                </g>
              </g>
            )}

            {series.length > 1 && (
              <>
                <text x={pad.l} y={H - 9} className="fill-muted-foreground" style={{ fontSize: 9 }}>{dateLabel(series[0].created_at)}</text>
                <text x={W - pad.r} y={H - 9} textAnchor="end" className="fill-muted-foreground" style={{ fontSize: 9 }}>{dateLabel(latestRun.created_at)}</text>
              </>
            )}
          </svg>
        </div>
      )}
    </Card>
  )
}

function VerdictDonut({ runs }: { runs: RunSummary[] }) {
  const [hovered, setHovered] = useState<RunSummary["verdict"] | null>(null)
  const counts = VERDICTS.map((verdict) => ({ verdict, count: runs.filter((run) => run.verdict === verdict).length }))
  const total = Math.max(1, runs.length)
  const radius = 54
  const circumference = 2 * Math.PI * radius
  let cumulative = 0
  const safeRuns = counts.filter(({ verdict }) => verdict === "Pass" || verdict === "Conditional pass").reduce((sum, item) => sum + item.count, 0)
  const active = hovered ? counts.find((item) => item.verdict === hovered) : null

  return (
    <Card className="overflow-hidden">
      <div className="flex items-start justify-between border-b border-border px-5 py-4">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck className="size-4 text-sev-ok" /> Verdict mix
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Release posture across recent runs</p>
        </div>
        <div className="rounded-full bg-muted px-2.5 py-1 font-mono text-[11px] text-muted-foreground tnum">
          {Math.round((safeRuns / total) * 100)}% releaseable
        </div>
      </div>
      <div className="grid min-h-[238px] items-center gap-3 px-5 py-4 sm:grid-cols-[190px_1fr]">
        <div className="relative mx-auto size-[176px]">
          <svg viewBox="0 0 176 176" className="size-full -rotate-90" role="img" aria-label="Verdict distribution donut chart">
            <circle cx="88" cy="88" r={radius} fill="none" stroke="hsl(var(--muted))" strokeWidth="17" />
            {counts.map(({ verdict, count }) => {
              const length = (count / total) * circumference
              const offset = -cumulative * circumference
              cumulative += count / total
              if (!count) return null
              return (
                <circle
                  key={verdict}
                  cx="88"
                  cy="88"
                  r={radius}
                  fill="none"
                  stroke={verdictColor(verdict)}
                  strokeWidth={hovered === verdict ? 21 : 17}
                  strokeDasharray={`${length} ${circumference - length}`}
                  strokeDashoffset={offset}
                  strokeLinecap="round"
                  className="cursor-pointer transition-all"
                  onMouseEnter={() => setHovered(verdict)}
                  onMouseLeave={() => setHovered(null)}
                />
              )
            })}
          </svg>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="font-mono text-3xl font-semibold tnum">{active?.count ?? runs.length}</span>
            <span className="max-w-20 text-[10px] uppercase leading-tight tracking-wide text-muted-foreground">
              {active?.verdict ?? "recent runs"}
            </span>
          </div>
        </div>
        <div className="grid gap-2">
          {counts.map(({ verdict, count }) => (
            <button
              type="button"
              key={verdict}
              onMouseEnter={() => setHovered(verdict)}
              onMouseLeave={() => setHovered(null)}
              className={`group flex items-center gap-3 rounded-lg border px-3 py-2 text-left transition-colors ${hovered === verdict ? "border-foreground/25 bg-muted/60" : "border-transparent hover:bg-muted/40"}`}
            >
              <span className="size-2.5 shrink-0 rounded-full" style={{ background: verdictColor(verdict), boxShadow: `0 0 0 4px color-mix(in srgb, ${verdictColor(verdict)} 12%, transparent)` }} />
              <span className="min-w-0 flex-1 text-xs text-muted-foreground group-hover:text-foreground">{verdict}</span>
              <span className="font-mono text-sm font-semibold tnum">{count}</span>
              <span className="w-9 text-right font-mono text-[10px] text-muted-foreground tnum">{Math.round((count / total) * 100)}%</span>
            </button>
          ))}
        </div>
      </div>
    </Card>
  )
}

export function DashboardCharts({ runs }: { runs: RunSummary[] }) {
  return (
    <div className="grid gap-3 xl:grid-cols-[1.35fr_.85fr]">
      <RiTrend runs={runs} />
      <VerdictDonut runs={runs} />
    </div>
  )
}
