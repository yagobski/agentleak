import { useCallback, useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import {
  Activity,
  Bot,
  FolderKanban,
  Gauge,
  ScanLine,
  ScrollText,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  UserCog,
  Users,
  Zap,
} from "lucide-react"
import { toast } from "sonner"
import {
  api,
  type AdminOverview,
  type AdminUsage,
  type AdminUser,
  type AuditLogEntry,
} from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { riVerdict, scoreColor, verdictColor } from "@/lib/format"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Switch } from "@/components/ui/switch"
import { PageHeader } from "@/layout/AppShell"
import { RunRow } from "@/features/RunRow"

function Stat({ label, value, icon, sub }: { label: string; value: React.ReactNode; icon: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <Card>
      <CardHeader className="relative space-y-0 p-4 pb-2">
        <CardDescription className="text-[11px] font-medium uppercase tracking-wide">{label}</CardDescription>
        <CardTitle className="font-mono text-3xl tabular-nums tnum">{value}</CardTitle>
        <div className="absolute right-4 top-4 text-muted-foreground/70">{icon}</div>
      </CardHeader>
      {sub && <CardContent className="p-4 pt-0 text-xs text-muted-foreground">{sub}</CardContent>}
    </Card>
  )
}

export function Admin() {
  const { user: me } = useAuth()
  const nav = useNavigate()
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [users, setUsers] = useState<AdminUser[]>([])
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([])
  const [usage, setUsage] = useState<AdminUsage | null>(null)
  const [error, setError] = useState("")

  const reload = useCallback(() => {
    api.adminOverview().then(setOverview).catch((e) => setError(e.message))
    api.adminUsers().then(setUsers).catch(() => {})
    api.adminAuditLog().then(setAuditLog).catch(() => {})
    api.adminUsage().then(setUsage).catch(() => {})
  }, [])
  useEffect(reload, [reload])

  async function toggleAdmin(u: AdminUser) {
    try {
      await api.adminUpdateUser(u.id, { is_admin: !u.is_admin })
      toast.success(u.is_admin ? `${u.email} is no longer admin` : `${u.email} promoted to admin`)
      reload()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  async function toggleDisabled(u: AdminUser) {
    try {
      await api.adminUpdateUser(u.id, { disabled: !u.disabled })
      toast.success(u.disabled ? `${u.email} re-enabled` : `${u.email} disabled — sessions revoked`)
      reload()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  async function removeUser(u: AdminUser) {
    if (!window.confirm(`Delete ${u.email} and ALL their projects/runs? This cannot be undone.`)) return
    try {
      await api.adminDeleteUser(u.id)
      toast.success(`${u.email} deleted`)
      reload()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  if (error) {
    return (
      <div className="animate-fade-up">
        <PageHeader title="Administration" description="Platform-wide management." />
        <Card className="p-10 text-center text-sm text-sev-l4">{error}</Card>
      </div>
    )
  }

  const avg = overview?.avg_risk_index

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Administration"
        description="Accounts, usage, and platform health — across every user of this deployment."
      />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <Stat
          label="Accounts"
          value={overview?.users ?? "—"}
          icon={<Users className="size-4" />}
          sub={overview ? `${overview.admins} admin(s) · ${overview.disabled_users} disabled` : undefined}
        />
        <Stat
          label="Projects"
          value={overview?.projects ?? "—"}
          icon={<FolderKanban className="size-4" />}
          sub="across all accounts"
        />
        <Stat
          label="Runs"
          value={overview?.runs ?? "—"}
          icon={<Activity className="size-4" />}
          sub={
            avg != null ? (
              <span>
                avg RI{" "}
                <span className="font-mono tnum" style={{ color: verdictColor(riVerdict(avg)) }}>
                  {avg.toFixed(3)}
                </span>{" "}
                · {overview?.blocked_runs} blocked
              </span>
            ) : (
              "no runs yet"
            )
          }
        />
        <Stat
          label="Code scans"
          value={overview?.code_scans ?? "—"}
          icon={<ScanLine className="size-4" />}
          sub="static source audits"
        />
        <Stat
          label="Agent API calls"
          value={overview?.api_calls_total ?? "—"}
          icon={<Zap className="size-4" />}
          sub={overview ? `${overview.api_calls_24h} in the last 24h` : "self-test / improve / register"}
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_380px]">
        <Card>
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <span className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
              <UserCog className="size-3.5" /> Accounts
            </span>
            <Badge variant="muted">{users.length}</Badge>
          </div>
          <div className="divide-y divide-border/60">
            {users.map((u) => (
              <div key={u.id} className="flex flex-wrap items-center gap-3 px-5 py-3 text-sm">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`truncate font-medium ${u.disabled ? "text-muted-foreground line-through" : ""}`}>
                      {u.email}
                    </span>
                    {u.is_admin && (
                      <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-primary">
                        admin
                      </span>
                    )}
                    {u.disabled && (
                      <span className="rounded bg-sev-l4/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-sev-l4">
                        disabled
                      </span>
                    )}
                    {u.id === me?.id && (
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase text-muted-foreground">you</span>
                    )}
                  </div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {u.project_count} project(s) · {u.run_count} run(s)
                    {u.created_at ? ` · joined ${new Date(u.created_at * 1000).toLocaleDateString()}` : ""}
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Switch
                      checked={u.is_admin ?? false}
                      onCheckedChange={() => toggleAdmin(u)}
                      disabled={u.id === me?.id}
                    />
                    admin
                  </label>
                  <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Switch
                      checked={!u.disabled}
                      onCheckedChange={() => toggleDisabled(u)}
                      disabled={u.id === me?.id}
                    />
                    active
                  </label>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removeUser(u)}
                    disabled={u.id === me?.id}
                    title="Delete account and all its data"
                  >
                    <Trash2 className="size-3.5 text-sev-l4" />
                  </Button>
                </div>
              </div>
            ))}
            {users.length === 0 && (
              <div className="px-5 py-8 text-center text-sm text-muted-foreground">Loading accounts…</div>
            )}
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <span className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
              {overview && overview.blocked_runs > 0 ? (
                <ShieldAlert className="size-3.5 text-sev-l4" />
              ) : (
                <ShieldCheck className="size-3.5 text-sev-ok" />
              )}
              Recent activity (all users)
            </span>
            <Gauge className="size-3.5 text-muted-foreground" />
          </div>
          <div className="max-h-[480px] overflow-auto">
            {(overview?.recent_runs ?? []).map((r) => (
              <RunRow key={r.id} run={r} onClick={() => nav(`/runs/${r.id}`)} />
            ))}
            {overview && overview.recent_runs.length === 0 && (
              <div className="px-5 py-8 text-center text-sm text-muted-foreground">No runs yet.</div>
            )}
          </div>
        </Card>
      </div>

      <Card className="mt-4">
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <span className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            <Bot className="size-3.5" /> Agent activity — runs &amp; API consumption per project
          </span>
          <Badge variant="muted">{usage?.projects.length ?? 0}</Badge>
        </div>

        {usage && usage.daily.some((d) => d.runs > 0 || d.api_calls > 0) && (
          <div className="flex items-end gap-1 border-b border-border/60 px-5 py-3">
            {usage.daily.map((d) => {
              const max = Math.max(1, ...usage.daily.map((x) => Math.max(x.runs, x.api_calls)))
              return (
                <div key={d.date} className="flex flex-1 flex-col items-center gap-0.5" title={`${d.date}: ${d.runs} runs, ${d.api_calls} API calls`}>
                  <div className="flex h-12 w-full items-end gap-0.5">
                    <div
                      className="flex-1 rounded-sm bg-primary/60"
                      style={{ height: `${Math.max(2, (d.runs / max) * 100)}%` }}
                    />
                    <div
                      className="flex-1 rounded-sm bg-sev-l2/60"
                      style={{ height: `${Math.max(2, (d.api_calls / max) * 100)}%` }}
                    />
                  </div>
                  <span className="text-[9px] text-muted-foreground">{d.date.slice(5)}</span>
                </div>
              )
            })}
          </div>
        )}
        <div className="flex items-center gap-4 border-b border-border/60 px-5 py-2 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5"><span className="size-2 rounded-sm bg-primary/60" /> runs</span>
          <span className="flex items-center gap-1.5"><span className="size-2 rounded-sm bg-sev-l2/60" /> agent API calls</span>
          <span>last 14 days</span>
        </div>

        <div className="divide-y divide-border/40">
          {(usage?.projects ?? []).map((p) => (
            <div key={p.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-2.5 text-xs">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate font-medium">{p.name}</span>
                  <span className="text-muted-foreground">{p.owner_email}</span>
                </div>
                <div className="mt-0.5 text-muted-foreground">
                  {p.run_count} run(s)
                  {p.last_run_at ? ` · last run ${new Date(p.last_run_at * 1000).toLocaleString()}` : ""}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-4">
                {p.avg_privacy_score != null && (
                  <span className="tnum font-semibold" style={{ color: scoreColor(p.avg_privacy_score) }}>
                    {Math.round(p.avg_privacy_score)}/100
                  </span>
                )}
                {p.blocked_runs > 0 && (
                  <span className="rounded bg-sev-l4/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-sev-l4">
                    {p.blocked_runs} blocked
                  </span>
                )}
                <span className="flex items-center gap-1 text-muted-foreground">
                  <Zap className="size-3" /> {p.api_call_count} API call(s)
                </span>
                <span className="text-muted-foreground">{p.scan_count} scan(s)</span>
              </div>
            </div>
          ))}
          {usage && usage.projects.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-muted-foreground">
              No projects have run yet.
            </div>
          )}
        </div>
      </Card>

      <Card className="mt-4">
        <div className="flex items-center justify-between border-b border-border px-5 py-3">
          <span className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            <ScrollText className="size-3.5" /> Audit log
          </span>
          <Badge variant="muted">{auditLog.length}</Badge>
        </div>
        <div className="max-h-80 divide-y divide-border/40 overflow-auto">
          {auditLog.map((entry) => (
            <div key={entry.id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-2.5 text-xs">
              <div className="min-w-0">
                <span className="font-mono font-medium">{entry.action}</span>{" "}
                <span className="text-muted-foreground">
                  by {entry.actor_email} on {entry.target_email || entry.target_id}
                </span>
                {entry.detail && <span className="ml-2 text-muted-foreground">({entry.detail})</span>}
              </div>
              <span className="shrink-0 text-muted-foreground">
                {new Date(entry.created_at * 1000).toLocaleString()}
              </span>
            </div>
          ))}
          {auditLog.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-muted-foreground">
              No admin actions recorded yet.
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
