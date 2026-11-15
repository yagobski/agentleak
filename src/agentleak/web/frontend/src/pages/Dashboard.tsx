// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Rows3, ScanSearch } from "lucide-react"
import { api, type LeaderboardEntry, type Stats } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { DataTable, type Column } from "@/components/DataTable"
import { VerdictLabel } from "@/features/Chips"
import { formatStamp, RunsTable, type RunRow } from "@/features/RunsTable"
import { PageHeader } from "@/layout/AppShell"

const FIRST_SCENARIO = "healthcare_patient_summary"

function Stat({ label, value, note }: { label: string; value: React.ReactNode; note?: string }) {
  return (
    <div className="min-w-0 border-border py-1 sm:border-l sm:pl-4 sm:first:border-l-0 sm:first:pl-0">
      <dt className="text-[12px] text-muted-foreground">{label}</dt>
      <dd className="mt-1 font-mono text-2xl leading-none tnum">{value}</dd>
      {note && <dd className="mt-1 text-[11px] text-muted-foreground">{note}</dd>}
    </div>
  )
}

export function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [board, setBoard] = useState<LeaderboardEntry[] | null>(null)
  const [names, setNames] = useState<Record<string, string>>({})
  const [error, setError] = useState("")

  useEffect(() => {
    api.stats().then(setStats).catch((e) => setError((e as Error).message))
    api.leaderboard().then((r) => setBoard(r.entries)).catch(() => setBoard([]))
    api
      .projects()
      .then((ps) => setNames(Object.fromEntries(ps.map((p) => [p.id, p.name]))))
      .catch(() => {})
  }, [])

  const recent: RunRow[] = (stats?.recent_runs ?? []).map((r) => ({ ...r, project_name: names[r.project_id] }))
  const empty = stats !== null && stats.runs === 0

  const boardColumns: Column<LeaderboardEntry>[] = [
    {
      id: "project",
      header: "Project",
      value: (e) => e.name,
      cell: (e) => (
        <Link to={`/projects/${e.project_id}`} className="block max-w-[22rem] truncate underline decoration-border underline-offset-2 hover:decoration-foreground" title={e.name} onClick={(ev) => ev.stopPropagation()}>
          {e.name}
        </Link>
      ),
    },
    { id: "verdict", header: "Latest verdict", value: (e) => e.verdict, cell: (e) => <VerdictLabel verdict={e.verdict} /> },
    { id: "risk_index", header: "Latest RI", value: (e) => e.risk_index, align: "right", cell: (e) => <span className="font-mono text-[12px]">{e.risk_index.toFixed(3)}</span> },
    { id: "privacy_score", header: "Score", value: (e) => e.privacy_score, align: "right", hideBelow: "sm", cell: (e) => <span className="font-mono text-[12px]">{e.privacy_score}</span> },
    { id: "runs", header: "Runs", value: (e) => e.runs, align: "right", cell: (e) => <span className="font-mono text-[12px]">{e.runs}</span> },
    { id: "last_run_at", header: "Last run", value: (e) => e.last_run_at ?? 0, hideBelow: "md", cell: (e) => <span className="font-mono text-[11px] text-muted-foreground">{e.last_run_at ? formatStamp(e.last_run_at) : "–"}</span> },
  ]

  return (
    <div className="min-w-0">
      <PageHeader
        title="Dashboard"
        description="Latest AgentRisk results across the projects in this workspace."
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="/runs">
                <Rows3 /> All runs
              </Link>
            </Button>
            <Button asChild>
              <Link to="/analyze">
                <ScanSearch /> Analyze a trace
              </Link>
            </Button>
          </>
        }
      />

      {error && <p role="alert" className="mb-4 text-sm text-sev-l4">Could not load workspace statistics: {error}</p>}

      {empty ? (
        <section className="max-w-2xl rounded-lg border border-border bg-card p-5">
          <h2 className="text-base font-medium">No runs yet</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            The fastest first result: score a bundled healthcare trace whose final answer is clean while its shared memory,
            inter-agent messages and logs are not.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button asChild>
              <Link to={`/analyze?scenario=${FIRST_SCENARIO}`}>
                <ScanSearch /> Analyze <code className="font-mono text-[12px]">{FIRST_SCENARIO}</code>
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/analyze">Use your own trace file</Link>
            </Button>
          </div>
          <p className="mt-3 text-[12px] text-muted-foreground">
            From code: <code className="font-mono">agentleak run --scenario {FIRST_SCENARIO}</code>
          </p>
        </section>
      ) : (
        <>
          <dl className="mb-6 grid grid-cols-2 gap-4 rounded-lg border border-border bg-card p-4 sm:grid-cols-4">
            <Stat label="Projects" value={stats?.projects ?? "–"} />
            <Stat label="Stored runs" value={stats?.runs ?? "–"} />
            <Stat
              label="Blocked runs"
              value={
                stats ? (
                  <>
                    {stats.blocked_runs}
                    <span className="text-base text-muted-foreground"> / {stats.runs}</span>
                  </>
                ) : (
                  "–"
                )
              }
              note="runs a CI gate would fail"
            />
            <Stat
              label="Mean Risk Index"
              value={stats?.avg_risk_index != null ? stats.avg_risk_index.toFixed(3) : "–"}
              note={stats ? `over ${stats.runs} runs, all scenarios mixed` : undefined}
            />
          </dl>

          <section aria-labelledby="dash-projects" className="mb-6">
            <h2 id="dash-projects" className="mb-2 text-sm font-medium">Latest result per project</h2>
            <div className="rounded-lg border border-border bg-card">
              <DataTable
                caption="Latest result per project"
                columns={boardColumns}
                rows={board ?? []}
                rowKey={(e) => e.project_id}
                initialSort={{ id: "risk_index", dir: "desc" }}
                exportName="projects-latest"
                empty={board === null ? "Loading…" : "No project has a run yet."}
              />
            </div>
          </section>

          <section aria-labelledby="dash-recent">
            <div className="mb-2 flex items-baseline justify-between gap-2">
              <h2 id="dash-recent" className="text-sm font-medium">Recent runs</h2>
              <Link to="/runs" className="text-[12px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline">
                {stats ? `All ${stats.runs} runs` : "All runs"}
              </Link>
            </div>
            <div className="rounded-lg border border-border bg-card">
              <RunsTable runs={recent} exportName="recent-runs" caption="Recent runs" pageSize={0} />
            </div>
          </section>
        </>
      )}
    </div>
  )
}
