// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react"
import { Link, useNavigate } from "react-router-dom"
import { GitCompareArrows, Search } from "lucide-react"
import { api, type Report, type RunSummary } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { DataTable, type Column } from "@/components/DataTable"
import { VerdictLabel } from "./Chips"

export type RunRow = RunSummary & { project_name?: string }

/** The most recent runs in the workspace, across projects (newest first, one request). */
export function useAllRuns(limit = 200) {
  const [runs, setRuns] = useState<RunRow[] | null>(null)
  const [total, setTotal] = useState(0)
  const [error, setError] = useState("")
  const load = useCallback(() => {
    setError("")
    api
      .runsPage({ limit, sort: "created_at", dir: "desc" })
      .then((p) => {
        setRuns(p.items)
        setTotal(p.total)
      })
      .catch((e) => setError((e as Error).message))
  }, [limit])
  useEffect(load, [load])
  return { runs, total, error, reload: load }
}

export function formatStamp(epoch: number): string {
  const d = new Date(epoch * 1000)
  const pad = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const VERDICTS: Report["verdict"][] = ["Pass", "Conditional pass", "High risk", "Fail"]

export function RunsTable({
  runs,
  showProject = true,
  caption = "Runs",
  exportName = "runs",
  pageSize = 50,
  extraColumns = [],
  toolbarExtra,
  compare = true,
  empty,
}: {
  runs: RunRow[]
  showProject?: boolean
  caption?: string
  exportName?: string
  pageSize?: number
  extraColumns?: Column<RunRow>[]
  toolbarExtra?: ReactNode
  compare?: boolean
  empty?: ReactNode
}) {
  const nav = useNavigate()
  const [q, setQ] = useState("")
  const [verdict, setVerdict] = useState("all")
  const [selected, setSelected] = useState<string[]>([])

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return runs.filter((r) => {
      if (verdict !== "all" && r.verdict !== verdict) return false
      if (needle && !`${r.id} ${r.agent_name} ${r.label ?? ""} ${r.project_name ?? ""} ${r.source}`.toLowerCase().includes(needle)) return false
      return true
    })
  }, [runs, q, verdict])

  const columns: Column<RunRow>[] = [
    {
      id: "run_id",
      header: "Run",
      value: (r) => r.id,
      cell: (r) => (
        <Link to={`/runs/${r.id}`} className="font-mono text-[12px] underline decoration-border underline-offset-2 hover:decoration-foreground" onClick={(e) => e.stopPropagation()}>
          {r.id}
        </Link>
      ),
    },
    ...(showProject
      ? [
          {
            id: "project",
            header: "Project",
            value: (r: RunRow) => r.project_name ?? r.project_id,
            hideBelow: "md",
            cell: (r: RunRow) => <span className="block max-w-[14rem] truncate" title={r.project_name}>{r.project_name ?? r.project_id}</span>,
          } satisfies Column<RunRow>,
        ]
      : []),
    {
      id: "agent",
      header: "Agent",
      value: (r) => r.agent_name,
      cell: (r) => (
        <span className="block max-w-[16rem] truncate font-mono text-[12px]" title={r.agent_name}>
          {r.agent_name || "–"}
          {r.label ? <span className="ml-1.5 font-sans text-muted-foreground">{r.label}</span> : null}
        </span>
      ),
    },
    { id: "verdict", header: "Verdict", value: (r) => r.verdict, cell: (r) => <VerdictLabel verdict={r.verdict} /> },
    { id: "risk_index", header: "RI", value: (r) => r.risk_index, align: "right", cell: (r) => <span className="font-mono text-[12px]">{r.risk_index.toFixed(3)}</span> },
    { id: "privacy_score", header: "Score", value: (r) => r.privacy_score, align: "right", hideBelow: "sm", cell: (r) => <span className="font-mono text-[12px]">{r.privacy_score}</span> },
    { id: "leaked_secrets", header: "Leaked", value: (r) => r.leaked_secrets, align: "right", hideBelow: "sm", cell: (r) => <span className="font-mono text-[12px]">{r.leaked_secrets}</span> },
    {
      id: "blocked",
      header: "Gate",
      value: (r) => (r.blocked ? "blocked" : "passed"),
      hideBelow: "md",
      cell: (r) => (r.blocked ? <span className="text-[12px] font-medium text-sev-l4">blocked</span> : <span className="text-[12px] text-muted-foreground">passed</span>),
    },
    { id: "source", header: "Source", value: (r) => r.source, hideBelow: "lg", cell: (r) => <span className="font-mono text-[11px] text-muted-foreground">{r.source}</span> },
    { id: "created", header: "Stored", value: (r) => r.created_at, hideBelow: "md", cell: (r) => <span className="whitespace-nowrap font-mono text-[11px] text-muted-foreground">{formatStamp(r.created_at)}</span> },
    ...extraColumns,
  ]

  return (
    <DataTable
      caption={caption}
      columns={columns}
      rows={rows}
      rowKey={(r) => r.id}
      initialSort={{ id: "created", dir: "desc" }}
      exportName={exportName}
      pageSize={pageSize}
      onRowClick={(r) => nav(`/runs/${r.id}`)}
      empty={runs.length ? "No run matches these filters." : empty ?? "No runs yet."}
      selection={compare ? { selected, onChange: setSelected, max: 2, label: (r) => r.id } : undefined}
      toolbar={
        <>
          <div className="relative min-w-[160px] flex-1 sm:max-w-[16rem]">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Run, agent, label, project" aria-label="Search runs" data-shortcut="search" className="h-8 pl-8 text-[13px]" />
          </div>
          <label className="sr-only" htmlFor={`verdict-${exportName}`}>
            Verdict
          </label>
          <select id={`verdict-${exportName}`} value={verdict} onChange={(e) => setVerdict(e.target.value)} className="h-8 rounded-md border border-input bg-background px-2 text-[13px]">
            <option value="all">All verdicts</option>
            {VERDICTS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
          {compare && (
            <Button
              size="sm"
              variant={selected.length === 2 ? "default" : "outline"}
              className="h-8"
              disabled={selected.length !== 2}
              onClick={() => {
                // Oldest first, so "A → B" reads as before → after.
                const [a, b] = [...selected].sort(
                  (x, y) => (runs.find((r) => r.id === x)?.created_at ?? 0) - (runs.find((r) => r.id === y)?.created_at ?? 0),
                )
                nav(`/compare?a=${a}&b=${b}`)
              }}
            >
              <GitCompareArrows /> Compare {selected.length}/2
            </Button>
          )}
          {toolbarExtra}
        </>
      }
    />
  )
}
