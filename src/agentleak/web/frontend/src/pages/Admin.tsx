// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useCallback, useEffect, useMemo, useState } from "react"
import { RefreshCw, Search } from "lucide-react"
import { toast } from "sonner"
import {
  api,
  type AdminDailyUsage,
  type AdminEndpointUsage,
  type AdminOverview,
  type AdminProjectUsage,
  type AdminUsage,
  type AdminUser,
  type AuditLogEntry,
  type Meta,
  type RunSummary,
} from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { DataTable, type Column } from "@/components/DataTable"
import { Section, Stat } from "@/components/Section"
import { VerdictLabel } from "@/features/Chips"
import { formatStamp } from "@/features/RunsTable"
import { PageHeader } from "@/layout/AppShell"

function Filter({ id, value, onChange, label }: { id: string; value: string; onChange: (v: string) => void; label: string }) {
  return (
    <div className="relative min-w-[140px] flex-1 sm:max-w-[14rem]">
      <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
      <Input id={id} value={value} onChange={(e) => onChange(e.target.value)} placeholder={label} aria-label={label} className="h-8 pl-8 text-[13px]" />
    </div>
  )
}

const num = (n: number | null | undefined) => <span className="font-mono text-[12px]">{n ?? "–"}</span>

export function Admin() {
  const { user: me } = useAuth()
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [users, setUsers] = useState<AdminUser[] | null>(null)
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([])
  const [usage, setUsage] = useState<AdminUsage | null>(null)
  const [meta, setMeta] = useState<Meta | null>(null)
  const [error, setError] = useState("")
  const [refreshing, setRefreshing] = useState(false)
  const [answeredAt, setAnsweredAt] = useState<Date | null>(null)
  const [accountQuery, setAccountQuery] = useState("")
  const [projectQuery, setProjectQuery] = useState("")
  const [auditQuery, setAuditQuery] = useState("")
  const [toDelete, setToDelete] = useState<AdminUser | null>(null)

  const reload = useCallback(async () => {
    setRefreshing(true)
    setError("")
    try {
      const [o, u, a, us, m] = await Promise.all([api.adminOverview(), api.adminUsers(), api.adminAuditLog(), api.adminUsage(), api.meta()])
      setOverview(o)
      setUsers(u)
      setAuditLog(a)
      setUsage(us)
      setMeta(m)
      setAnsweredAt(new Date())
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setRefreshing(false)
    }
  }, [])
  useEffect(() => {
    reload()
  }, [reload])

  async function update(user: AdminUser, body: { is_admin?: boolean; disabled?: boolean }, done: string) {
    try {
      await api.adminUpdateUser(user.id, body)
      toast.success(done)
      reload()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  async function removeUser(user: AdminUser) {
    try {
      await api.adminDeleteUser(user.id)
      toast.success(`Deleted ${user.email}`)
      reload()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const filteredUsers = useMemo(
    () => (users ?? []).filter((u) => `${u.email} ${u.name}`.toLowerCase().includes(accountQuery.trim().toLowerCase())),
    [users, accountQuery],
  )
  const filteredProjects = useMemo(
    () => (usage?.projects ?? []).filter((p) => `${p.name} ${p.owner_email}`.toLowerCase().includes(projectQuery.trim().toLowerCase())),
    [usage, projectQuery],
  )
  const filteredAudit = useMemo(
    () => auditLog.filter((e) => `${e.action} ${e.actor_email} ${e.target_email} ${e.detail}`.toLowerCase().includes(auditQuery.trim().toLowerCase())),
    [auditLog, auditQuery],
  )

  const self = (u: AdminUser) => u.id === me?.id
  const userColumns: Column<AdminUser>[] = [
    {
      id: "email",
      header: "Account",
      value: (u) => u.email,
      cell: (u) => (
        <span className="block max-w-[18rem] truncate" title={u.email}>
          <span className={u.disabled ? "text-muted-foreground line-through" : undefined}>{u.email}</span>
          {self(u) && <span className="ml-1.5 text-[11px] text-muted-foreground">(you)</span>}
        </span>
      ),
    },
    { id: "role", header: "Role", value: (u) => (u.is_admin ? "admin" : "member"), cell: (u) => <span className="text-[12px]">{u.is_admin ? "admin" : "member"}</span> },
    {
      id: "state",
      header: "State",
      value: (u) => (u.disabled ? "disabled" : "active"),
      cell: (u) => <span className={u.disabled ? "text-[12px] font-medium text-sev-l4" : "text-[12px] text-muted-foreground"}>{u.disabled ? "disabled" : "active"}</span>,
    },
    { id: "projects", header: "Projects", value: (u) => u.project_count, align: "right", cell: (u) => num(u.project_count) },
    { id: "runs", header: "Runs", value: (u) => u.run_count, align: "right", cell: (u) => num(u.run_count) },
    {
      id: "joined",
      header: "Joined",
      value: (u) => u.created_at ?? 0,
      hideBelow: "md",
      cell: (u) => <span className="whitespace-nowrap font-mono text-[11px] text-muted-foreground">{u.created_at ? formatStamp(u.created_at) : "–"}</span>,
    },
    {
      id: "actions",
      header: "",
      value: () => "",
      sortable: false,
      exportable: false,
      cell: (u) =>
        self(u) ? (
          <span className="text-[11px] text-muted-foreground">your account</span>
        ) : (
          <span className="flex flex-wrap justify-end gap-1">
            <Button
              size="sm"
              variant="outline"
              className="h-7 px-2 text-[12px]"
              aria-label={`${u.is_admin ? "Remove admin role from" : "Make admin"} ${u.email}`}
              onClick={() => update(u, { is_admin: !u.is_admin }, u.is_admin ? `${u.email} is no longer an admin` : `${u.email} is now an admin`)}
            >
              {u.is_admin ? "Remove admin" : "Make admin"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-7 px-2 text-[12px]"
              aria-label={`${u.disabled ? "Enable" : "Disable"} ${u.email}`}
              onClick={() => update(u, { disabled: !u.disabled }, u.disabled ? `${u.email} enabled` : `${u.email} disabled; its sessions are revoked`)}
            >
              {u.disabled ? "Enable" : "Disable"}
            </Button>
            <Button size="sm" variant="ghost" className="h-7 px-2 text-[12px] text-sev-l4 hover:text-sev-l4" aria-label={`Delete ${u.email}`} onClick={() => setToDelete(u)}>
              Delete
            </Button>
          </span>
        ),
    },
  ]

  const runColumns: Column<RunSummary>[] = [
    { id: "run", header: "Run", value: (r) => r.id, cell: (r) => <span className="font-mono text-[12px]">{r.id}</span> },
    { id: "verdict", header: "Verdict", value: (r) => r.verdict, cell: (r) => <VerdictLabel verdict={r.verdict} /> },
    { id: "ri", header: "RI", value: (r) => r.risk_index, align: "right", cell: (r) => <span className="font-mono text-[12px]">{r.risk_index.toFixed(3)}</span> },
    { id: "leaked", header: "Leaked", value: (r) => r.leaked_secrets, align: "right", hideBelow: "sm", cell: (r) => num(r.leaked_secrets) },
    { id: "gate", header: "Gate", value: (r) => (r.blocked ? "blocked" : "passed"), hideBelow: "sm", cell: (r) => <span className={r.blocked ? "text-[12px] font-medium text-sev-l4" : "text-[12px] text-muted-foreground"}>{r.blocked ? "blocked" : "passed"}</span> },
    { id: "source", header: "Source", value: (r) => r.source, hideBelow: "md", cell: (r) => <span className="font-mono text-[11px] text-muted-foreground">{r.source}</span> },
    { id: "stored", header: "Stored", value: (r) => r.created_at, cell: (r) => <span className="whitespace-nowrap font-mono text-[11px] text-muted-foreground">{formatStamp(r.created_at)}</span> },
  ]

  const projectColumns: Column<AdminProjectUsage>[] = [
    { id: "project", header: "Project", value: (p) => p.name, cell: (p) => <span className="block max-w-[16rem] truncate" title={p.name}>{p.name}</span> },
    { id: "owner", header: "Owner", value: (p) => p.owner_email, hideBelow: "md", cell: (p) => <span className="block max-w-[14rem] truncate text-[12px] text-muted-foreground">{p.owner_email || "–"}</span> },
    { id: "runs", header: "Runs", value: (p) => p.run_count, align: "right", cell: (p) => num(p.run_count) },
    { id: "blocked", header: "Blocked", value: (p) => p.blocked_runs, align: "right", cell: (p) => <span className="font-mono text-[12px]">{p.blocked_runs} / {p.run_count}</span> },
    {
      id: "mean_score",
      header: "Mean score",
      value: (p) => p.avg_privacy_score,
      align: "right",
      hideBelow: "sm",
      cell: (p) => <span className="font-mono text-[12px]" title={`Mean over ${p.run_count} runs, which may be of different scenarios`}>{p.avg_privacy_score != null ? Math.round(p.avg_privacy_score) : "–"}</span>,
    },
    { id: "scans", header: "Code scans", value: (p) => p.scan_count, align: "right", hideBelow: "md", cell: (p) => num(p.scan_count) },
    { id: "api", header: "Agent API", value: (p) => p.api_call_count, align: "right", hideBelow: "md", cell: (p) => num(p.api_call_count) },
    { id: "last_run", header: "Last run", value: (p) => p.last_run_at ?? 0, hideBelow: "lg", cell: (p) => <span className="whitespace-nowrap font-mono text-[11px] text-muted-foreground">{p.last_run_at ? formatStamp(p.last_run_at) : "never"}</span> },
  ]

  const endpointColumns: Column<AdminEndpointUsage>[] = [
    { id: "endpoint", header: "Endpoint", value: (e) => e.endpoint, cell: (e) => <code className="break-all font-mono text-[12px]">{e.endpoint}</code> },
    { id: "count", header: "Calls", value: (e) => e.count, align: "right", cell: (e) => num(e.count) },
    { id: "projects", header: "Projects", value: (e) => e.projects, align: "right", cell: (e) => num(e.projects) },
    { id: "last", header: "Last call", value: (e) => e.last_called_at ?? 0, hideBelow: "sm", cell: (e) => <span className="whitespace-nowrap font-mono text-[11px] text-muted-foreground">{e.last_called_at ? formatStamp(e.last_called_at) : "–"}</span> },
  ]

  const dayColumns: Column<AdminDailyUsage>[] = [
    { id: "date", header: "Day (UTC)", value: (d) => d.date, cell: (d) => <span className="font-mono text-[12px]">{d.date}</span> },
    { id: "runs", header: "Runs", value: (d) => d.runs, align: "right", cell: (d) => num(d.runs) },
    { id: "blocked", header: "Blocked", value: (d) => d.blocked_runs, align: "right", cell: (d) => num(d.blocked_runs) },
    { id: "api", header: "Agent API calls", value: (d) => d.api_calls, align: "right", cell: (d) => num(d.api_calls) },
    { id: "scans", header: "Code scans", value: (d) => d.code_scans, align: "right", cell: (d) => num(d.code_scans) },
  ]

  const auditColumns: Column<AuditLogEntry>[] = [
    { id: "when", header: "When", value: (e) => e.created_at, cell: (e) => <span className="whitespace-nowrap font-mono text-[11px] text-muted-foreground">{formatStamp(e.created_at)}</span> },
    { id: "action", header: "Action", value: (e) => e.action, cell: (e) => <code className="font-mono text-[12px]">{e.action}</code> },
    { id: "actor", header: "By", value: (e) => e.actor_email, cell: (e) => <span className="block max-w-[14rem] truncate text-[12px]">{e.actor_email}</span> },
    { id: "target", header: "On", value: (e) => e.target_email || e.target_id, hideBelow: "sm", cell: (e) => <span className="block max-w-[14rem] truncate text-[12px]">{e.target_email || e.target_id || "–"}</span> },
    { id: "detail", header: "Detail", value: (e) => e.detail, hideBelow: "md", cell: (e) => <span className="break-words text-[12px] text-muted-foreground">{e.detail || "–"}</span> },
  ]

  const o = overview
  const header = (
    <PageHeader
      title="Administration"
      description="Accounts, usage and operations across every account on this deployment. Aggregate metadata only: no report, value or trace is shown here."
      actions={
        <Button variant="outline" size="sm" onClick={reload} disabled={refreshing}>
          <RefreshCw className={refreshing ? "animate-spin motion-reduce:animate-none" : undefined} /> Refresh
        </Button>
      }
    />
  )

  if (error && !o) {
    return (
      <div className="min-w-0">
        {header}
        <div className="max-w-xl rounded-lg border border-border p-5">
          <h2 className="text-base font-medium">Could not load the administration data</h2>
          <p className="mt-1 text-sm text-muted-foreground">{error}</p>
          <Button variant="outline" size="sm" className="mt-3" onClick={reload}>
            Retry
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-w-0 space-y-5">
      {header}
      <p className="text-[12px] text-muted-foreground" aria-live="polite">
        {answeredAt ? (
          <>
            The API answered at <time dateTime={answeredAt.toISOString()}>{answeredAt.toLocaleTimeString()}</time> · AgentLeak{" "}
            <span className="font-mono">{meta?.version ?? "–"}</span>
            {o?.last_activity_at ? ` · last run stored ${formatStamp(o.last_activity_at)}` : " · no run stored yet"}
          </>
        ) : (
          "Loading…"
        )}
      </p>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 rounded-lg border border-border bg-card p-4 sm:grid-cols-3 xl:grid-cols-6">
        <Stat label="Accounts" value={o?.users ?? "–"} note={o ? `${o.admins} admin, ${o.disabled_users} disabled` : undefined} />
        <Stat label="Projects" value={o?.projects ?? "–"} note={o ? `${o.active_projects_24h} of ${o.projects} active in 24 h` : undefined} />
        <Stat label="Runs" value={o?.runs ?? "–"} note={o ? `${o.runs_24h} in 24 h, ${o.redteam_runs} red team` : undefined} />
        <Stat label="Blocked runs" value={o ? `${o.blocked_runs} / ${o.runs}` : "–"} note={o ? `${o.blocked_24h} of ${o.runs_24h} in 24 h` : undefined} />
        <Stat
          label="Mean privacy score"
          value={o?.avg_privacy_score != null ? Math.round(o.avg_privacy_score) : "–"}
          note={o?.avg_risk_index != null ? `mean RI ${o.avg_risk_index.toFixed(3)} over ${o.runs} runs, all accounts and scenarios` : "no runs yet"}
        />
        <Stat label="Code scans / agent API calls" value={o ? `${o.code_scans} / ${o.api_calls_total}` : "–"} note={o ? `${o.code_scans_24h} / ${o.api_calls_24h} in 24 h` : undefined} />
      </dl>

      <Section title="Accounts" description="Disabling an account ends its sessions; its projects' API keys stop working until it is enabled again.">
        <DataTable
          caption="Accounts"
          columns={userColumns}
          rows={filteredUsers}
          rowKey={(u) => u.id}
          initialSort={{ id: "joined", dir: "asc" }}
          exportName="accounts"
          empty={users === null ? "Loading accounts…" : "No account matches this filter."}
          toolbar={<Filter id="admin-accounts" value={accountQuery} onChange={setAccountQuery} label="Filter accounts" />}
        />
      </Section>

      <div className="grid min-w-0 gap-5 xl:grid-cols-2">
        <Section title="Recent runs" description="The 15 latest runs of every account. Runs open only from their owner's workspace.">
          <DataTable caption="Recent runs, all accounts" columns={runColumns} rows={o?.recent_runs ?? []} rowKey={(r) => r.id} initialSort={{ id: "stored", dir: "desc" }} empty="No run stored yet." />
        </Section>
        <Section title="Last 14 days" description="Per UTC day.">
          <DataTable caption="Activity per day, last 14 days" columns={dayColumns} rows={usage?.daily ?? []} rowKey={(d) => d.date} initialSort={{ id: "date", dir: "desc" }} exportName="daily-activity" />
        </Section>
      </div>

      <Section title="Projects" description="Busiest first. A mean score mixes every scenario the project ran.">
        <DataTable
          caption="Usage per project"
          columns={projectColumns}
          rows={filteredProjects}
          rowKey={(p) => p.id}
          exportName="projects-usage"
          pageSize={50}
          empty={usage === null ? "Loading…" : "No project matches this filter."}
          toolbar={<Filter id="admin-projects" value={projectQuery} onChange={setProjectQuery} label="Filter projects or owners" />}
        />
      </Section>

      <div className="grid min-w-0 gap-5 xl:grid-cols-2">
        <Section title="Agent API endpoints">
          <DataTable caption="Agent API calls per endpoint" columns={endpointColumns} rows={usage?.endpoints ?? []} rowKey={(e) => e.endpoint} initialSort={{ id: "count", dir: "desc" }} empty="No agent API call yet." />
        </Section>
        <Section title="Admin audit log" description="Role changes, disables and deletions, newest first.">
          <DataTable
            caption="Admin audit log"
            columns={auditColumns}
            rows={filteredAudit}
            rowKey={(e) => e.id}
            initialSort={{ id: "when", dir: "desc" }}
            exportName="admin-audit-log"
            pageSize={25}
            empty={auditLog.length ? "No entry matches this filter." : "No admin action recorded yet."}
            toolbar={<Filter id="admin-audit" value={auditQuery} onChange={setAuditQuery} label="Filter the audit log" />}
          />
        </Section>
      </div>

      <ConfirmDialog
        open={!!toDelete}
        onOpenChange={(v) => !v && setToDelete(null)}
        title={`Delete ${toDelete?.email ?? "this account"}?`}
        description={`The account, its ${toDelete?.project_count ?? 0} project(s), ${toDelete?.run_count ?? 0} run(s), scenarios, triage decisions and sessions are removed. This cannot be undone.`}
        confirmLabel="Delete account"
        onConfirm={async () => {
          if (toDelete) await removeUser(toDelete)
        }}
      />
    </div>
  )
}
