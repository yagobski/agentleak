// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { GitCompareArrows, Search, X } from "lucide-react"
import { toast } from "sonner"
import { api, type Project, type Report, type RunPage, type RunQuery } from "@/lib/api"
import { download } from "@/lib/format"
import { toCsv } from "@/lib/export"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { DataTable, type Column, type SortState } from "@/components/DataTable"
import { VerdictLabel } from "./Chips"
import { formatStamp, type RunRow } from "./RunsTable"

const VERDICTS: Report["verdict"][] = ["Pass", "Conditional pass", "High risk", "Fail"]
const PAGE_SIZE = 50
const EXPORT_MAX = 10_000
// Table column id -> server sort key.
const SORT_KEYS: Record<string, string> = {
  created: "created_at",
  risk_index: "risk_index",
  privacy_score: "privacy_score",
  leaked_secrets: "leaked_secrets",
  verdict: "verdict",
  agent: "agent_name",
  project: "project",
}

/** Local calendar day -> Unix seconds at its local midnight. */
export function dayStart(day: string): number | undefined {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return undefined
  const [y, m, d] = day.split("-").map(Number)
  const t = new Date(y, m - 1, d).getTime()
  return Number.isNaN(t) ? undefined : Math.floor(t / 1000)
}

/** The filter in the URL -> the API query (the "to" day is inclusive). */
export function queryFromParams(p: URLSearchParams): RunQuery {
  const to = dayStart(p.get("to") ?? "")
  const sortId = p.get("sort") ?? "created"
  return {
    project: p.get("project") || undefined,
    verdict: p.get("verdict") || undefined,
    gate: (p.get("gate") as RunQuery["gate"]) || undefined,
    source: p.get("source") || undefined,
    since: dayStart(p.get("from") ?? ""),
    until: to === undefined ? undefined : to + 86_400,
    q: p.get("q")?.trim() || undefined,
    sort: SORT_KEYS[sortId] ?? "created_at",
    dir: p.get("dir") === "asc" ? "asc" : "desc",
    limit: PAGE_SIZE,
    offset: Math.max(0, Number(p.get("page") ?? 0) || 0) * PAGE_SIZE,
  }
}

const FILTER_KEYS = ["project", "verdict", "gate", "source", "from", "to", "q"]

/** Every run the account owns, paged and filtered by the server; the filter lives in the URL. */
export function RunsBrowser({ empty }: { empty?: ReactNode }) {
  const nav = useNavigate()
  const [params, setParams] = useSearchParams()
  const [page, setPage] = useState<RunPage | null>(null)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [projects, setProjects] = useState<Project[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const stamps = useRef(new Map<string, number>())
  const [qDraft, setQDraft] = useState(params.get("q") ?? "")

  const query = useMemo(() => queryFromParams(params), [params])
  const key = JSON.stringify(query)

  useEffect(() => {
    api.projects().then(setProjects).catch(() => {})
  }, [])

  useEffect(() => {
    let live = true
    setBusy(true)
    setError("")
    api
      .runsPage(query)
      .then((p) => {
        if (!live) return
        setPage(p)
        p.items.forEach((r) => stamps.current.set(r.id, r.created_at))
      })
      .catch((e) => live && setError((e as Error).message))
      .finally(() => live && setBusy(false))
    return () => {
      live = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  // Debounced search box -> URL.
  useEffect(() => {
    const t = window.setTimeout(() => {
      if ((params.get("q") ?? "") !== qDraft) update({ q: qDraft || null, page: null })
    }, 300)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qDraft])

  function update(next: Record<string, string | null>) {
    setParams(
      (prev) => {
        const p = new URLSearchParams(prev)
        for (const [k, v] of Object.entries(next)) {
          if (v === null || v === "") p.delete(k)
          else p.set(k, v)
        }
        return p
      },
      { replace: true },
    )
  }

  const filtered = FILTER_KEYS.some((k) => params.get(k))
  const total = page?.total ?? 0
  const sortId = params.get("sort") ?? "created"
  const sort: SortState = { id: sortId, dir: params.get("dir") === "asc" ? "asc" : "desc" }

  async function exportAll(format: "csv" | "json") {
    try {
      const res = await api.exportRuns(query, format)
      const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")
      const file = `runs-${stamp}.${format}`
      download(file, res.body, format === "csv" ? "text/csv;charset=utf-8" : "application/json")
      toast.success(
        res.exported < res.total
          ? `Exported the first ${res.exported} of ${res.total} matching runs to ${file}`
          : `Exported ${res.exported} matching run${res.exported === 1 ? "" : "s"} to ${file}`,
      )
    } catch (e) {
      toast.error(`Export failed: ${(e as Error).message}`)
    }
  }

  function exportPage() {
    const rows = page?.items ?? []
    const headers = ["run_id", "project", "agent", "label", "verdict", "risk_index", "privacy_score", "leaked_secrets", "gate", "source", "stored_at_utc"]
    const body = toCsv(
      headers,
      rows.map((r) => [r.id, r.project_name, r.agent_name, r.label ?? "", r.verdict, r.risk_index, r.privacy_score, r.leaked_secrets, r.blocked ? "blocked" : "passed", r.source, new Date(r.created_at * 1000).toISOString()]),
    )
    download(`runs-page-${(Number(params.get("page") ?? 0) || 0) + 1}.csv`, body, "text/csv;charset=utf-8")
    toast.success(`Exported the ${rows.length} rows on this page`)
  }

  const columns: Column<RunRow>[] = [
    {
      id: "run_id",
      header: "Run",
      value: (r) => r.id,
      sortable: false,
      cell: (r) => (
        <Link to={`/runs/${r.id}`} className="font-mono text-[12px] underline decoration-border underline-offset-2 hover:decoration-foreground" onClick={(e) => e.stopPropagation()}>
          {r.id}
        </Link>
      ),
    },
    {
      id: "project",
      header: "Project",
      value: (r) => r.project_name ?? r.project_id,
      hideBelow: "md",
      cell: (r) => <span className="block max-w-[14rem] truncate" title={r.project_name}>{r.project_name ?? r.project_id}</span>,
    },
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
      sortable: false,
      hideBelow: "md",
      cell: (r) => (r.blocked ? <span className="text-[12px] font-medium text-sev-l4">blocked</span> : <span className="text-[12px] text-muted-foreground">passed</span>),
    },
    { id: "source", header: "Source", value: (r) => r.source, sortable: false, hideBelow: "lg", cell: (r) => <span className="font-mono text-[11px] text-muted-foreground">{r.source}</span> },
    { id: "created", header: "Stored", value: (r) => r.created_at, hideBelow: "md", cell: (r) => <span className="whitespace-nowrap font-mono text-[11px] text-muted-foreground">{formatStamp(r.created_at)}</span> },
  ]

  const select = "h-8 rounded-md border border-input bg-background px-2 text-[13px]"
  const exportLabel = total > EXPORT_MAX ? `first ${EXPORT_MAX} of ${total} matching rows` : `all ${total} matching row${total === 1 ? "" : "s"}`

  return (
    <div className="min-w-0">
      {error && (
        <p role="alert" className="border-b border-border px-4 py-2 text-sm text-sev-l4">
          Could not load runs: {error}
        </p>
      )}
      {page === null && !error ? (
        <div className="space-y-2 p-4" aria-busy="true">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-7 rounded bg-muted motion-safe:animate-pulse" />
          ))}
        </div>
      ) : (
        <DataTable
          caption="Runs"
          columns={columns}
          rows={page?.items ?? []}
          rowKey={(r) => r.id}
          exportName="runs"
          exportMenu={[
            { label: `CSV, ${exportLabel}`, onSelect: () => exportAll("csv") },
            { label: `JSON, ${exportLabel}`, onSelect: () => exportAll("json") },
            { label: `CSV, the ${page?.items.length ?? 0} rows on this page`, onSelect: exportPage },
          ]}
          manual={{
            sort,
            onSort: (s) => update({ sort: s ? s.id : null, dir: s ? s.dir : null, page: null }),
            total,
            page: Number(params.get("page") ?? 0) || 0,
            pageSize: PAGE_SIZE,
            onPage: (p) => update({ page: p ? String(p) : null }),
            busy,
          }}
          onRowClick={(r) => nav(`/runs/${r.id}`)}
          empty={filtered ? "No run matches these filters." : empty ?? "No runs yet."}
          selection={{ selected, onChange: setSelected, max: 2, label: (r) => r.id }}
          toolbar={
            <>
              <div className="relative min-w-[160px] flex-1 sm:max-w-[14rem]">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={qDraft}
                  onChange={(e) => setQDraft(e.target.value)}
                  maxLength={200}
                  placeholder="Run, agent, label, project"
                  aria-label="Search runs"
                  data-shortcut="search"
                  className="h-8 pl-8 text-[13px]"
                />
              </div>
              <div className="grid w-full grid-cols-2 gap-2 sm:contents">
              <label className="sr-only" htmlFor="runs-project">Project</label>
              <select id="runs-project" value={params.get("project") ?? ""} onChange={(e) => update({ project: e.target.value, page: null })} className={`${select} w-full min-w-0 sm:w-auto sm:max-w-[12rem]`}>
                <option value="">All projects</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
              <label className="sr-only" htmlFor="runs-verdict">Verdict</label>
              <select id="runs-verdict" value={params.get("verdict") ?? ""} onChange={(e) => update({ verdict: e.target.value, page: null })} className={`${select} w-full min-w-0 sm:w-auto`}>
                <option value="">All verdicts</option>
                {VERDICTS.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
              <label className="sr-only" htmlFor="runs-gate">Gate</label>
              <select id="runs-gate" value={params.get("gate") ?? ""} onChange={(e) => update({ gate: e.target.value, page: null })} className={`${select} w-full min-w-0 sm:w-auto`}>
                <option value="">Gate: any</option>
                <option value="blocked">Blocked</option>
                <option value="passed">Passed</option>
              </select>
              <label className="sr-only" htmlFor="runs-source">Source</label>
              <select id="runs-source" value={params.get("source") ?? ""} onChange={(e) => update({ source: e.target.value, page: null })} className={`${select} w-full min-w-0 sm:w-auto`}>
                <option value="">All sources</option>
                {(page?.sources ?? []).map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <span className="col-span-2 inline-flex items-center gap-1 text-[12px] text-muted-foreground">
                <label htmlFor="runs-from">From</label>
                <input id="runs-from" type="date" value={params.get("from") ?? ""} max={params.get("to") ?? undefined} onChange={(e) => update({ from: e.target.value, page: null })} className={`${select} min-w-0 flex-1 sm:w-[8.5rem] sm:flex-none`} />
                <label htmlFor="runs-to">to</label>
                <input id="runs-to" type="date" value={params.get("to") ?? ""} min={params.get("from") ?? undefined} onChange={(e) => update({ to: e.target.value, page: null })} className={`${select} min-w-0 flex-1 sm:w-[8.5rem] sm:flex-none`} />
              </span>
              </div>
              {filtered && (
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8"
                  onClick={() => {
                    setQDraft("")
                    update(Object.fromEntries([...FILTER_KEYS, "page"].map((k) => [k, null])))
                  }}
                >
                  <X /> Clear filters
                </Button>
              )}
              <Button
                size="sm"
                variant={selected.length === 2 ? "default" : "outline"}
                className="h-8"
                disabled={selected.length !== 2}
                onClick={() => {
                  // Oldest first, so "A → B" reads as before → after.
                  const [a, b] = [...selected].sort((x, y) => (stamps.current.get(x) ?? 0) - (stamps.current.get(y) ?? 0))
                  nav(`/compare?a=${a}&b=${b}`)
                }}
              >
                <GitCompareArrows /> Compare {selected.length}/2
              </Button>
            </>
          }
        />
      )}
    </div>
  )
}
