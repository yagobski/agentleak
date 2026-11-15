// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react"
import { api, type Progression, type RunHistoryEntry } from "@/lib/api"
import { scoreColor } from "@/lib/format"

/** Privacy score per run over time, with the aggregate it is read against. */
export function ProgressionView({ projectId }: { projectId: string }) {
  const [history, setHistory] = useState<RunHistoryEntry[]>([])
  const [prog, setProg] = useState<Progression | null>(null)

  useEffect(() => {
    let active = true
    api
      .history(projectId)
      .then((h) => {
        if (!active) return
        setHistory(h.runs)
        setProg("total_runs" in h.progression ? (h.progression as Progression) : null)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [projectId])

  if (history.length < 2) return null
  const scenarios = new Set(history.map((r) => r.agent_name)).size

  return (
    <section aria-labelledby="progression" className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="progression" className="text-sm font-medium">Privacy score per run</h2>
        {prog && (
          <dl className="flex flex-wrap gap-x-4 text-[12px] text-muted-foreground">
            <div className="flex gap-1"><dt>latest</dt><dd className="font-mono text-foreground tnum">{prog.latest_score}/100</dd></div>
            <div className="flex gap-1"><dt>best</dt><dd className="font-mono text-foreground tnum">{prog.best_score}/100</dd></div>
            <div className="flex gap-1"><dt>blocked</dt><dd className="font-mono text-foreground tnum">{prog.blocked_runs} of {prog.total_runs}</dd></div>
          </dl>
        )}
      </div>
      {scenarios > 1 && (
        <p className="mb-2 text-[12px] text-muted-foreground">
          These runs come from {scenarios} different agents or scenarios, so the line is not a trend. To check a change, compare two runs of the same scenario.
        </p>
      )}
      <ScoreTrend runs={history} />
    </section>
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

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-3xl" role="img" aria-label="Privacy score over runs">
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
        <path d={line} fill="none" stroke="hsl(var(--muted-foreground))" strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
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
    </div>
  )
}

