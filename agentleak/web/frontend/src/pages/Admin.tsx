import { useCallback, useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Activity, Bot, Clock3, FileSearch, FolderKanban, Gauge, RefreshCw, ScanLine, ScrollText, Search, Server, ShieldAlert, ShieldCheck, Trash2, UserCog, Users, Zap } from "lucide-react"
import { toast } from "sonner"
import { api, type AdminOverview, type AdminUsage, type AdminUser, type AuditLogEntry, type Meta, type RunSummary } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { riVerdict, scoreColor, verdictColor } from "@/lib/format"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"
import { AgentLeakMark } from "@/features/AgentLeakLogo"
import { timeAgo, VerdictChip } from "@/features/RunRow"
import { PageHeader } from "@/layout/AppShell"

function Stat({ label, value, icon, sub }: { label: string; value: React.ReactNode; icon: React.ReactNode; sub?: React.ReactNode }) {
  return <Card className="min-w-0"><CardHeader className="relative min-w-0 space-y-0 p-4 pb-2"><CardDescription className="truncate text-[11px] font-medium uppercase tracking-wide">{label}</CardDescription><CardTitle className="truncate font-mono text-3xl tabular-nums tnum">{value}</CardTitle><div className="absolute right-4 top-4 text-muted-foreground/70">{icon}</div></CardHeader>{sub && <CardContent className="min-w-0 truncate p-4 pt-0 text-xs text-muted-foreground">{sub}</CardContent>}</Card>
}

function SectionHeader({ icon, title, count, children }: { icon: React.ReactNode; title: string; count?: number; children?: React.ReactNode }) {
  return <div className="flex min-w-0 flex-wrap items-center justify-between gap-2 border-b border-border px-5 py-3"><span className="flex min-w-0 items-center gap-2 text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">{icon}<span className="truncate">{title}</span></span><div className="flex items-center gap-2">{children}{count != null && <Badge variant="muted">{count}</Badge>}</div></div>
}

function RecentRun({ run, onClick }: { run: RunSummary; onClick: () => void }) {
  return <button onClick={onClick} className="grid w-full min-w-0 gap-2 border-b border-border/50 px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-accent/40">
    <div className="flex min-w-0 flex-wrap items-center gap-2"><VerdictChip verdict={run.verdict} ri={run.risk_index} /><span className="font-mono text-sm font-semibold" style={{ color: scoreColor(run.privacy_score) }}>{run.privacy_score}<small className="text-[10px] text-muted-foreground">/100</small></span>{run.blocked && <span className="rounded border border-sev-l4/30 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-sev-l4">blocked</span>}</div>
    <div className="min-w-0"><div className="truncate text-xs font-medium" title={run.label || run.agent_name}>{run.label || run.agent_name || "agent"}</div><div className="mt-1 flex min-w-0 flex-wrap gap-x-2 gap-y-1 text-[11px] text-muted-foreground"><span>{run.leaked_secrets} leaked</span><span className="min-w-0 break-all">{run.source}</span><span>{timeAgo(run.created_at)}</span></div></div>
  </button>
}

export function Admin() {
  const { user: me } = useAuth()
  const nav = useNavigate()
  const [overview, setOverview] = useState<AdminOverview | null>(null)
  const [users, setUsers] = useState<AdminUser[]>([])
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([])
  const [usage, setUsage] = useState<AdminUsage | null>(null)
  const [meta, setMeta] = useState<Meta | null>(null)
  const [error, setError] = useState("")
  const [refreshing, setRefreshing] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const [accountQuery, setAccountQuery] = useState("")
  const [projectQuery, setProjectQuery] = useState("")
  const [auditQuery, setAuditQuery] = useState("")

  const reload = useCallback(async () => {
    setRefreshing(true)
    setError("")
    try {
      const [nextOverview, nextUsers, nextAudit, nextUsage, nextMeta] = await Promise.all([api.adminOverview(), api.adminUsers(), api.adminAuditLog(), api.adminUsage(), api.meta()])
      setOverview(nextOverview); setUsers(nextUsers); setAuditLog(nextAudit); setUsage(nextUsage); setMeta(nextMeta); setLastUpdated(new Date())
    } catch (loadError) { setError((loadError as Error).message) }
    finally { setRefreshing(false) }
  }, [])
  useEffect(() => { reload() }, [reload])

  async function toggleAdmin(user: AdminUser) { try { await api.adminUpdateUser(user.id, { is_admin: !user.is_admin }); toast.success(user.is_admin ? `${user.email} is no longer admin` : `${user.email} promoted to admin`); reload() } catch (actionError) { toast.error((actionError as Error).message) } }
  async function toggleDisabled(user: AdminUser) { try { await api.adminUpdateUser(user.id, { disabled: !user.disabled }); toast.success(user.disabled ? `${user.email} re-enabled` : `${user.email} disabled — sessions revoked`); reload() } catch (actionError) { toast.error((actionError as Error).message) } }
  async function removeUser(user: AdminUser) { if (!window.confirm(`Delete ${user.email} and ALL their projects/runs? This cannot be undone.`)) return; try { await api.adminDeleteUser(user.id); toast.success(`${user.email} deleted`); reload() } catch (actionError) { toast.error((actionError as Error).message) } }

  const filteredUsers = useMemo(() => users.filter((user) => `${user.email} ${user.name}`.toLowerCase().includes(accountQuery.toLowerCase())), [users, accountQuery])
  const filteredProjects = useMemo(() => (usage?.projects ?? []).filter((project) => `${project.name} ${project.owner_email}`.toLowerCase().includes(projectQuery.toLowerCase())), [usage, projectQuery])
  const filteredAudit = useMemo(() => auditLog.filter((entry) => `${entry.action} ${entry.actor_email} ${entry.target_email} ${entry.detail}`.toLowerCase().includes(auditQuery.toLowerCase())), [auditLog, auditQuery])
  const avg = overview?.avg_risk_index
  const blockedRate = overview?.runs ? (overview.blocked_runs / overview.runs) * 100 : 0
  const activeRate = overview?.projects ? ((overview.active_projects_24h / overview.projects) * 100) : 0
  const dailyMax = Math.max(1, ...(usage?.daily ?? []).map((item) => Math.max(item.runs, item.api_calls, item.code_scans)))

  if (error && !overview) return <div className="animate-fade-up"><PageHeader title="Administration" description="Platform-wide management." /><Card className="p-10 text-center text-sm text-sev-l4">{error}<Button variant="outline" size="sm" className="ml-3" onClick={reload}>Retry</Button></Card></div>

  return <div className="animate-fade-up min-w-0 overflow-hidden">
    <PageHeader title="Administration" description="Security posture, accounts, usage, target activity and platform operations." actions={<div className="flex items-center gap-3"><span className="hidden text-[11px] text-muted-foreground sm:inline">{lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : "Loading platform state…"}</span><Button variant="outline" size="sm" onClick={reload} disabled={refreshing}><RefreshCw className={`size-3.5 ${refreshing ? "animate-spin" : ""}`} /> Refresh</Button></div>} />

    <Card className="mb-4 overflow-hidden border-primary/20 bg-primary/[0.025]"><div className="flex min-w-0 flex-wrap items-center gap-x-5 gap-y-3 px-4 py-3"><AgentLeakMark className="!h-7 !w-6" label="" /><div className="flex min-w-0 flex-1 items-center gap-2"><Server className="size-4 text-sev-ok" /><div className="min-w-0"><p className="text-xs font-semibold">Platform operational</p><p className="truncate text-[11px] text-muted-foreground">AgentLeak {meta?.version ?? "—"} · API, storage and authentication responded successfully</p></div></div><div className="flex flex-wrap gap-2 text-[10px]"><span className="rounded-full bg-sev-ok/10 px-2 py-1 text-sev-ok">healthy</span><span className="rounded-full bg-muted px-2 py-1 text-muted-foreground">{overview?.active_projects_24h ?? 0} active targets / 24h</span><span className="rounded-full bg-muted px-2 py-1 text-muted-foreground">{overview?.redteam_runs ?? 0} red-team runs</span>{overview?.last_activity_at && <span className="rounded-full bg-muted px-2 py-1 text-muted-foreground">last run {timeAgo(overview.last_activity_at)}</span>}</div></div></Card>

    <div className="grid min-w-0 grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6">
      <Stat label="Accounts" value={overview?.users ?? "—"} icon={<Users className="size-4" />} sub={overview ? `${overview.admins} admin · ${overview.disabled_users} disabled` : undefined} />
      <Stat label="Projects" value={overview?.projects ?? "—"} icon={<FolderKanban className="size-4" />} sub={overview ? `${overview.active_projects_24h} active in 24h` : "all targets"} />
      <Stat label="Runs" value={overview?.runs ?? "—"} icon={<Activity className="size-4" />} sub={overview ? `${overview.runs_24h} in 24h · ${overview.redteam_runs} red-team` : "all evaluations"} />
      <Stat label="Privacy score" value={overview?.avg_privacy_score != null ? Math.round(overview.avg_privacy_score) : "—"} icon={<Gauge className="size-4" />} sub={avg != null ? <span>avg RI <span className="font-mono" style={{ color: verdictColor(riVerdict(avg)) }}>{avg.toFixed(3)}</span></span> : "no runs yet"} />
      <Stat label="Code scans" value={overview?.code_scans ?? "—"} icon={<ScanLine className="size-4" />} sub={overview ? `${overview.code_scans_24h} in the last 24h` : "static source audits"} />
      <Stat label="Agent API calls" value={overview?.api_calls_total ?? "—"} icon={<Zap className="size-4" />} sub={overview ? `${overview.api_calls_24h} in the last 24h` : "autonomous consumption"} />
    </div>

    <div className="mt-4 grid min-w-0 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Card className="p-4"><p className="text-[10px] uppercase tracking-wide text-muted-foreground">Blocked posture</p><div className="mt-2 flex items-end justify-between"><strong className="font-mono text-2xl text-sev-l4">{blockedRate.toFixed(1)}%</strong><span className="text-xs text-muted-foreground">{overview?.blocked_runs ?? 0}/{overview?.runs ?? 0} runs</span></div><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full bg-sev-l4" style={{ width: `${Math.min(100, blockedRate)}%` }} /></div></Card>
      <Card className="p-4"><p className="text-[10px] uppercase tracking-wide text-muted-foreground">24-hour activity</p><div className="mt-3 grid grid-cols-3 gap-2 text-center"><div><strong className="block font-mono text-lg">{overview?.runs_24h ?? 0}</strong><small className="text-muted-foreground">runs</small></div><div><strong className="block font-mono text-lg">{overview?.api_calls_24h ?? 0}</strong><small className="text-muted-foreground">API</small></div><div><strong className="block font-mono text-lg">{overview?.code_scans_24h ?? 0}</strong><small className="text-muted-foreground">scans</small></div></div></Card>
      <Card className="p-4"><p className="text-[10px] uppercase tracking-wide text-muted-foreground">Target adoption</p><div className="mt-2 flex items-end justify-between"><strong className="font-mono text-2xl">{activeRate.toFixed(0)}%</strong><span className="text-xs text-muted-foreground">active / 24h</span></div><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full bg-primary" style={{ width: `${Math.min(100, activeRate)}%` }} /></div></Card>
      <Card className="p-4"><p className="text-[10px] uppercase tracking-wide text-muted-foreground">Current alerts</p><div className="mt-3 flex items-center gap-3">{(overview?.blocked_24h ?? 0) > 0 ? <ShieldAlert className="size-7 text-sev-l4" /> : <ShieldCheck className="size-7 text-sev-ok" />}<div><strong className="font-mono text-xl">{overview?.blocked_24h ?? 0}</strong><p className="text-xs text-muted-foreground">blocked runs in 24h</p></div></div></Card>
    </div>

    <div className="mt-4 grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,.85fr)]">
      <Card className="min-w-0 overflow-hidden"><SectionHeader icon={<UserCog className="size-3.5" />} title="Accounts"><div className="relative hidden sm:block"><Search className="absolute left-2 top-1/2 size-3 -translate-y-1/2 text-muted-foreground" /><Input value={accountQuery} onChange={(event) => setAccountQuery(event.target.value)} placeholder="Filter accounts" className="h-7 w-44 pl-7 text-xs" /></div><Badge variant="muted">{filteredUsers.length}</Badge></SectionHeader><div className="divide-y divide-border/60">{filteredUsers.map((user) => <div key={user.id} className="grid min-w-0 gap-3 px-5 py-3 text-sm md:grid-cols-[minmax(0,1fr)_auto] md:items-center"><div className="min-w-0"><div className="flex min-w-0 flex-wrap items-center gap-2"><span className={`min-w-0 truncate font-medium ${user.disabled ? "text-muted-foreground line-through" : ""}`}>{user.email}</span>{user.is_admin && <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-primary">admin</span>}{user.disabled && <span className="rounded bg-sev-l4/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-sev-l4">disabled</span>}{user.id === me?.id && <span className="rounded bg-muted px-1.5 py-0.5 text-[9px] uppercase text-muted-foreground">you</span>}</div><div className="mt-1 text-xs text-muted-foreground">{user.project_count} projects · {user.run_count} runs{user.created_at ? ` · joined ${new Date(user.created_at * 1000).toLocaleDateString()}` : ""}</div></div><div className="flex flex-wrap items-center gap-3"><label className="flex items-center gap-1.5 text-xs text-muted-foreground"><Switch checked={user.is_admin ?? false} onCheckedChange={() => toggleAdmin(user)} disabled={user.id === me?.id} /> admin</label><label className="flex items-center gap-1.5 text-xs text-muted-foreground"><Switch checked={!user.disabled} onCheckedChange={() => toggleDisabled(user)} disabled={user.id === me?.id} /> active</label><Button variant="ghost" size="icon" onClick={() => removeUser(user)} disabled={user.id === me?.id} title="Delete account and all its data"><Trash2 className="size-3.5 text-sev-l4" /></Button></div></div>)}{users.length === 0 && <div className="px-5 py-8 text-center text-sm text-muted-foreground">Loading accounts…</div>}</div></Card>

      <Card className="min-w-0 overflow-hidden"><SectionHeader icon={(overview?.blocked_runs ?? 0) > 0 ? <ShieldAlert className="size-3.5 text-sev-l4" /> : <ShieldCheck className="size-3.5 text-sev-ok" />} title="Recent activity"><Clock3 className="size-3.5 text-muted-foreground" /></SectionHeader><div className="max-h-[500px] min-w-0 overflow-y-auto overflow-x-hidden">{(overview?.recent_runs ?? []).map((run) => <RecentRun key={run.id} run={run} onClick={() => nav(`/runs/${run.id}`)} />)}{overview && overview.recent_runs.length === 0 && <div className="px-5 py-8 text-center text-sm text-muted-foreground">No runs yet.</div>}</div></Card>
    </div>

    <Card className="mt-4 min-w-0 overflow-hidden"><SectionHeader icon={<Activity className="size-3.5" />} title="14-day activity"><Badge variant="muted">runs · API · scans</Badge></SectionHeader><div className="flex min-w-0 items-end gap-1 overflow-hidden border-b border-border/60 px-3 py-4 sm:px-5">{(usage?.daily ?? []).map((day) => <div key={day.date} className="flex min-w-0 flex-1 flex-col items-center gap-1" title={`${day.date}: ${day.runs} runs (${day.blocked_runs} blocked), ${day.api_calls} API calls, ${day.code_scans} scans`}><div className="flex h-20 w-full min-w-0 items-end justify-center gap-px"><div className="w-1/3 max-w-3 rounded-t-sm bg-primary/70" style={{ height: `${Math.max(2, (day.runs / dailyMax) * 100)}%` }} /><div className="w-1/3 max-w-3 rounded-t-sm bg-sev-l2/65" style={{ height: `${Math.max(2, (day.api_calls / dailyMax) * 100)}%` }} /><div className="w-1/3 max-w-3 rounded-t-sm bg-muted-foreground/55" style={{ height: `${Math.max(2, (day.code_scans / dailyMax) * 100)}%` }} /></div><span className="hidden text-[9px] text-muted-foreground sm:block">{day.date.slice(5)}</span></div>)}</div><div className="flex flex-wrap gap-4 px-5 py-2 text-[11px] text-muted-foreground"><span className="flex items-center gap-1.5"><i className="size-2 rounded-sm bg-primary/70" /> runs</span><span className="flex items-center gap-1.5"><i className="size-2 rounded-sm bg-sev-l2/65" /> agent API</span><span className="flex items-center gap-1.5"><i className="size-2 rounded-sm bg-muted-foreground/55" /> code scans</span></div></Card>

    <div className="mt-4 grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(300px,.6fr)]">
      <Card className="min-w-0 overflow-hidden"><SectionHeader icon={<Bot className="size-3.5" />} title="Target and project consumption"><div className="relative hidden sm:block"><Search className="absolute left-2 top-1/2 size-3 -translate-y-1/2 text-muted-foreground" /><Input value={projectQuery} onChange={(event) => setProjectQuery(event.target.value)} placeholder="Filter targets" className="h-7 w-44 pl-7 text-xs" /></div><Badge variant="muted">{filteredProjects.length}</Badge></SectionHeader><div className="w-full overflow-x-auto"><div className="min-w-[760px]"><div className="grid grid-cols-[minmax(180px,1.4fr)_minmax(170px,1fr)_70px_80px_80px_100px] gap-3 border-b border-border/50 px-5 py-2 text-[10px] uppercase tracking-wide text-muted-foreground"><span>Target</span><span>Owner</span><span>Runs</span><span>Score</span><span>Scans</span><span>Agent API</span></div>{filteredProjects.map((project) => <div key={project.id} className="grid grid-cols-[minmax(180px,1.4fr)_minmax(170px,1fr)_70px_80px_80px_100px] items-center gap-3 border-b border-border/40 px-5 py-3 text-xs last:border-b-0"><div className="min-w-0"><div className="truncate font-medium">{project.name}</div><small className="text-muted-foreground">{project.last_run_at ? `last run ${timeAgo(project.last_run_at)}` : "never evaluated"}</small></div><span className="truncate text-muted-foreground" title={project.owner_email}>{project.owner_email}</span><span className="font-mono">{project.run_count}{project.blocked_runs > 0 && <small className="ml-1 text-sev-l4">({project.blocked_runs} blocked)</small>}</span><span className="font-mono font-semibold" style={{ color: project.avg_privacy_score != null ? scoreColor(project.avg_privacy_score) : undefined }}>{project.avg_privacy_score != null ? Math.round(project.avg_privacy_score) : "—"}</span><span className="font-mono">{project.scan_count}</span><span className="font-mono">{project.api_call_count}</span></div>)}{usage && usage.projects.length === 0 && <div className="px-5 py-8 text-center text-sm text-muted-foreground">No projects have run yet.</div>}</div></div></Card>

      <Card className="min-w-0 overflow-hidden"><SectionHeader icon={<Zap className="size-3.5" />} title="API consumption" count={usage?.endpoints.length ?? 0} /><div className="divide-y divide-border/40">{(usage?.endpoints ?? []).map((endpoint) => <div key={endpoint.endpoint} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] gap-3 px-4 py-3 text-xs"><div className="min-w-0"><code className="block truncate font-mono text-[11px]" title={endpoint.endpoint}>{endpoint.endpoint}</code><small className="text-muted-foreground">{endpoint.projects} project(s){endpoint.last_called_at ? ` · ${timeAgo(endpoint.last_called_at)}` : ""}</small></div><strong className="font-mono text-sm">{endpoint.count}</strong></div>)}{usage && usage.endpoints.length === 0 && <div className="px-5 py-8 text-center text-sm text-muted-foreground">No agent API consumption yet.</div>}</div></Card>
    </div>

    <Card className="mt-4 min-w-0 overflow-hidden"><SectionHeader icon={<ScrollText className="size-3.5" />} title="Admin audit log"><div className="relative hidden sm:block"><Search className="absolute left-2 top-1/2 size-3 -translate-y-1/2 text-muted-foreground" /><Input value={auditQuery} onChange={(event) => setAuditQuery(event.target.value)} placeholder="Filter audit log" className="h-7 w-44 pl-7 text-xs" /></div><Badge variant="muted">{filteredAudit.length}</Badge></SectionHeader><div className="max-h-80 divide-y divide-border/40 overflow-auto">{filteredAudit.map((entry) => <div key={entry.id} className="grid min-w-0 gap-2 px-5 py-2.5 text-xs md:grid-cols-[minmax(0,1fr)_auto]"><div className="min-w-0 break-words"><span className="font-mono font-medium">{entry.action}</span> <span className="text-muted-foreground">by {entry.actor_email} on {entry.target_email || entry.target_id}</span>{entry.detail && <span className="ml-2 text-muted-foreground">({entry.detail})</span>}</div><span className="shrink-0 text-muted-foreground">{new Date(entry.created_at * 1000).toLocaleString()}</span></div>)}{auditLog.length === 0 && <div className="px-5 py-8 text-center text-sm text-muted-foreground">No admin actions recorded yet.</div>}</div></Card>

    <div className="mt-4 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground"><FileSearch className="size-3.5" /><span>All values are aggregate operational metadata. Raw secrets and matched values are never shown in the administration console.</span></div>
  </div>
}
