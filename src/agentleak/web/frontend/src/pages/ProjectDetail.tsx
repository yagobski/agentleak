// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useCallback, useEffect, useId, useState } from "react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom"
import { Bot, Check, Copy, Eye, EyeOff, Loader2, Pencil, Play, Plug, Plus, RefreshCw, Trash2, Wrench, X } from "lucide-react"
import { toast } from "sonner"
import {
  api,
  type AgentConfig,
  type ConnectInfo,
  type CustomRule,
  type Project,
  type ProjectModel,
  type RunSummary,
  type Scenario,
  type ToolConfig,
  DETECTORS,
  DETECTOR_LABEL,
} from "@/lib/api"
import { agentLabel } from "@/lib/agents"
import { useAgentTypes } from "@/lib/hooks"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { ModelView } from "@/features/ModelView"
import { AgentCardView } from "@/features/AgentCardView"
import { ProgressionView } from "@/features/ProgressionView"
import { RedTeamView } from "@/features/RedTeamView"
import { RunsTable } from "@/features/RunsTable"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { FieldRow, Section, inputSm } from "@/components/Section"
import { channelSplit, useMeta } from "@/lib/meta"
import { PageHeader } from "@/layout/AppShell"

function scenarioLabel(scenario: Scenario) {
  const raw = scenario.name && scenario.name !== scenario.id
    ? scenario.name
    : scenario.id.replace(new RegExp(`^${scenario.domain}_`), "").replace(/_/g, " ")
  return raw.charAt(0).toUpperCase() + raw.slice(1)
}

export function ProjectDetail() {
  const { id = "" } = useParams()
  const nav = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [notFound, setNotFound] = useState(false)
  const [params, setParams] = useSearchParams()
  const tab = params.get("tab") ?? "audit"

  const reload = useCallback(() => {
    api.project(id).then(setProject).catch(() => setNotFound(true))
    api.projectRuns(id).then(setRuns).catch(() => {})
  }, [id])
  useEffect(reload, [reload])

  if (notFound)
    return (
      <div className="max-w-xl rounded-lg border border-border p-5">
        <h1 className="text-base font-medium">Project not found</h1>
        <p className="mt-1 text-sm text-muted-foreground">No project with id {id} exists in this workspace.</p>
        <Button asChild variant="outline" size="sm" className="mt-3"><Link to="/projects">All projects</Link></Button>
      </div>
    )
  if (!project) return <div className="h-40 rounded-lg bg-muted motion-safe:animate-pulse" aria-busy="true" aria-label="Loading project" />

  return (
    <div className="min-w-0">
      <PageHeader
        title={project.name}
        crumbs={[{ label: "Projects", to: "/projects" }, { label: project.name }]}
        description={
          <>
            <span className="mr-2 rounded border border-border px-1.5 py-0.5 text-[11px]">{agentLabel(project.agent_type)}</span>
            <span className="tnum">{project.run_count ?? runs.length} runs</span>
            {project.avg_risk_index != null ? <span className="tnum"> · mean RI {project.avg_risk_index.toFixed(3)}</span> : null}
            {project.description ? <span className="mt-1 block">{project.description}</span> : null}
          </>
        }
      />

      <Tabs value={tab} onValueChange={(v) => setParams((p) => { const n = new URLSearchParams(p); n.set("tab", v); return n })}>
        <div className="overflow-x-auto">
        <TabsList className="h-auto justify-start">
          <TabsTrigger value="audit">Test</TabsTrigger>
          <TabsTrigger value="card">Identity &amp; code</TabsTrigger>
          <TabsTrigger value="agents">Test agents ({project.config.agents?.length ?? 0})</TabsTrigger>
          <TabsTrigger value="model">System map</TabsTrigger>
          <TabsTrigger value="runs">Runs ({project.run_count ?? runs.length})</TabsTrigger>
          <TabsTrigger value="redteam">Adversarial</TabsTrigger>
          <TabsTrigger value="connect">Integrate</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>
        </div>

        <TabsContent value="audit">
          <AuditTab project={project} onRan={reload} />
        </TabsContent>
        <TabsContent value="card">
          <AgentCardView project={project} onChange={reload} />
        </TabsContent>
        <TabsContent value="agents">
          <AgentsTab project={project} onChange={reload} />
        </TabsContent>
        <TabsContent value="model">
          <ModelTab project={project} />
        </TabsContent>
        <TabsContent value="runs">
          <RunsTab projectId={project.id} runs={runs} onChange={reload} />
        </TabsContent>
        <TabsContent value="redteam">
          <RedTeamView projectId={project.id} />
        </TabsContent>
        <TabsContent value="connect">
          <ConnectTab project={project} />
        </TabsContent>
        <TabsContent value="settings">
          <SettingsTab project={project} onSaved={reload} onDeleted={() => nav("/projects")} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

// ---------------------------------------------------------------- Audit
function AuditTab({ project, onRan }: { project: Project; onRan: () => void }) {
  const nav = useNavigate()
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [scenarioId, setScenarioId] = useState("")
  const [trace, setTrace] = useState("")
  const [label, setLabel] = useState("")
  const [mode, setMode] = useState<"agent" | "trace">("agent")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.scenarios().then((s) => {
      setScenarios(s)
      if (s.length) {
        setScenarioId(s[0].id)
        loadTrace(s[0].id)
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function loadTrace(sid: string) {
    try {
      setTrace(JSON.stringify(await api.example(sid), null, 2))
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const agent = project.config.agent
  const live = !!agent?.model
  const pipeline = (project.config.agents?.length ?? 0) > 0
  const selected = scenarios.find((s) => s.id === scenarioId)

  async function runAgent() {
    setBusy(true)
    try {
      const r = await api.executeAgent(project.id, { scenario_id: scenarioId, label: label.trim() })
      toast.success(`Agent run ${r.verdict} · RI ${r.report.risk_index.toFixed(3)}`)
      onRan()
      nav(`/runs/${r.id}`)
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function runTrace() {
    let parsed: unknown
    try {
      parsed = JSON.parse(trace)
    } catch {
      return toast.error("Trace is not valid JSON")
    }
    setBusy(true)
    try {
      const r = await api.createRun(project.id, { trace: parsed, source: "manual", label: label.trim() })
      toast.success(`Run ${r.verdict} · RI ${r.report.risk_index.toFixed(3)}`)
      onRan()
      nav(`/runs/${r.id}`)
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="p-5">
      <div className="mb-4 grid max-w-xs grid-cols-2 gap-1.5 rounded-md bg-muted p-1">
        {(["agent", "trace"] as const).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
              mode === m ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {m === "agent" ? "Scenario harness" : "Analyze a trace"}
          </button>
        ))}
      </div>

      {mode === "agent" ? (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Run a controlled scenario inside AgentLeak. A configured model is called through the test harness; without
            one, AgentLeak builds a deterministic scripted trace to validate your detectors. This does not call your
            deployed application.
          </p>
          <div className="grid items-end gap-3 sm:grid-cols-[1fr_1fr_auto]">
            <div className="space-y-1.5">
              <Label className="text-xs">Scenario</Label>
              <Select value={scenarioId} onValueChange={setScenarioId}>
                <SelectTrigger>
                  <SelectValue placeholder="Pick a scenario" />
                </SelectTrigger>
                <SelectContent>
                  {scenarios.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {scenarioLabel(s)}
                      {s.has_spec ? "  ·  spec" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Label <span className="text-muted-foreground">(optional)</span></Label>
              <Input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="e.g. baseline, after-fix"
              />
            </div>
            <Button onClick={runAgent} disabled={busy || !scenarioId}>
              {busy ? <Loader2 className="animate-spin" /> : <Bot />} {pipeline ? "Run test pipeline" : live ? "Test configured model" : "Run scripted baseline"}
            </Button>
          </div>

          <div className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-xs">
            {pipeline ? (
              <>
                <Bot className="size-3.5 text-primary" />
                <span>
                  Test topology — {project.config.agents?.length} configured roles hand off in sequence inside AgentLeak.
                  Configure them in <b className="text-foreground">Test agents</b>; connect production traces in <b className="text-foreground">Integrate</b>.
                </span>
              </>
            ) : live ? (
              <>
                <Bot className="size-3.5 text-primary" />
                <span>
                  Model harness — <code className="font-mono">{agent?.model}</code>. AgentLeak sends the selected
                  scenario to this endpoint and captures its behavior; it does not discover your production app.
                </span>
              </>
            ) : (
              <span className="text-muted-foreground">
                Offline detector baseline — no model or application is executed. Add a scenario model endpoint in <b className="text-foreground">Settings</b> to test a model.
              </span>
            )}
          </div>
          {selected && !selected.has_spec && (
            <p className="text-[11px] text-muted-foreground">
              This sample has no executable spec, so AgentLeak derives the scripted baseline from its packaged trace.
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Paste evidence captured from your own application, SDK or telemetry pipeline. AgentLeak only analyzes the
            JSON you provide; it does not execute your agent. You can also load a packaged trace as a starting point.
          </p>
          <div className="grid gap-4 md:grid-cols-[240px_1fr]">
            <div className="space-y-1.5">
              <Label className="text-xs">Load scenario trace</Label>
              <Select value={scenarioId} onValueChange={(v) => { setScenarioId(v); loadTrace(v) }}>
                <SelectTrigger>
                  <SelectValue placeholder="Pick a scenario" />
                </SelectTrigger>
                <SelectContent>
                  {scenarios.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {scenarioLabel(s)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Label className="mt-2 block text-xs">Label <span className="text-muted-foreground">(optional)</span></Label>
              <Input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="e.g. baseline, after-fix"
              />
              <Button className="mt-2 w-full" onClick={runTrace} disabled={busy}>
                {busy ? <Loader2 className="animate-spin" /> : <Play />} Analyze this trace
              </Button>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Trace (JSON)</Label>
              <Textarea
                value={trace}
                onChange={(e) => setTrace(e.target.value)}
                spellCheck={false}
                className="h-72 font-mono text-[12px] leading-relaxed"
              />
            </div>
          </div>
        </div>
      )}
    </Card>
  )
}

// ---------------------------------------------------------------- Agents
const BLANK_AGENT = { name: "", role: "assistant", framework: "generic", description: "", base_url: "", model: "", api_key: "", tools: [] as ToolConfig[] }

function AgentsTab({ project, onChange }: { project: Project; onChange: () => void }) {
  const agentTypes = useAgentTypes()
  const agents = project.config.agents ?? []
  const [editing, setEditing] = useState<string | null>(null) // agent id, "new", or null
  const [form, setForm] = useState({ ...BLANK_AGENT })
  const [busy, setBusy] = useState(false)

  function startNew() {
    setForm({ ...BLANK_AGENT })
    setEditing("new")
  }
  function startEdit(a: AgentConfig) {
    setForm({
      name: a.name,
      role: a.role ?? "assistant",
      framework: a.framework,
      description: a.description ?? "",
      base_url: a.endpoint?.base_url ?? "",
      model: a.endpoint?.model ?? "",
      api_key: "",
      tools: (a.tools ?? []).map((t) => ({ ...t })),
    })
    setEditing(a.id)
  }

  async function submit() {
    if (!form.name.trim()) return toast.error("Agent name is required")
    setBusy(true)
    const tools = form.tools
      .map((t) => ({
        name: t.name.trim(),
        kind: t.kind,
        server: t.kind === "mcp" ? (t.server ?? "").trim() : "",
        description: (t.description ?? "").trim(),
      }))
      .filter((t) => t.name)
    const body = {
      name: form.name.trim(),
      role: form.role.trim() || "assistant",
      framework: form.framework,
      description: form.description.trim(),
      endpoint: { base_url: form.base_url.trim(), model: form.model.trim(), api_key: form.api_key },
      tools,
    }
    try {
      if (editing === "new") await api.addAgent(project.id, body)
      else if (editing) await api.updateAgent(project.id, editing, body)
      toast.success("Agent saved")
      setEditing(null)
      onChange()
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(a: AgentConfig) {
    if (!confirm(`Remove agent “${a.name}”?`)) return
    try {
      await api.removeAgent(project.id, a.id)
      toast.success("Agent removed")
      onChange()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-medium">Agents in the test topology</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Define the roles AgentLeak should orchestrate during controlled scenario tests. This does not discover or
              mirror your deployed system; use <b className="text-foreground">Integrate</b> to submit real traces.
            </p>
          </div>
          <Button size="sm" onClick={startNew}>
            <Plus /> Add agent
          </Button>
        </div>

        {agents.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">No test agents yet. Add roles only if you want AgentLeak to simulate a multi-agent handoff.</p>
        ) : (
          <div className="mt-4 space-y-2">
            {agents.map((a, i) => {
              const live = !!a.endpoint?.model
              return (
                <div key={a.id} className="flex items-center gap-3 rounded-lg border border-border px-3 py-2.5">
                  <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-[11px] text-muted-foreground">
                    {i + 1}
                  </span>
                  <Bot className="size-4 shrink-0 text-primary" />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-sm font-medium">{a.name}</span>
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                        {agentLabel(a.framework)}
                      </span>
                      <span className="text-[11px] text-muted-foreground">· {a.role ?? "assistant"}</span>
                      <span className="text-[11px] text-muted-foreground">· {live ? `live (${a.endpoint?.model})` : "scripted"}</span>
                    </div>
                    {a.description && <p className="truncate text-xs text-muted-foreground">{a.description}</p>}
                    {!!a.tools?.length && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {a.tools.map((t, ti) => (
                          <span
                            key={ti}
                            className="inline-flex items-center gap-1 rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground"
                          >
                            {t.kind === "mcp" ? <Plug className="size-2.5" /> : <Wrench className="size-2.5" />}
                            {t.name || "unnamed"}
                            {t.kind === "mcp" && t.server ? ` · ${t.server}` : ""}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <Button variant="ghost" size="icon" className="size-7" onClick={() => startEdit(a)}>
                    <Pencil className="size-3.5" />
                  </Button>
                  <Button variant="ghost" size="icon" className="size-7 text-sev-l4" onClick={() => remove(a)}>
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              )
            })}
          </div>
        )}
      </Card>

      {editing && (
        <Card className="space-y-4 p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium">{editing === "new" ? "New agent" : "Edit agent"}</h3>
            <Button variant="ghost" size="icon" className="size-7" onClick={() => setEditing(null)}>
              <X className="size-4" />
            </Button>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs">Name</Label>
              <Input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Researcher" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Role</Label>
              <Input value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))} placeholder="researcher" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Framework</Label>
              <Select value={form.framework} onValueChange={(v) => setForm((f) => ({ ...f, framework: v }))}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {agentTypes.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Model (optional)</Label>
              <Input value={form.model} onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))} placeholder="gpt-4o-mini" className="font-mono text-xs" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">Base URL (optional)</Label>
              <Input value={form.base_url} onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))} placeholder="https://api.openai.com/v1" className="font-mono text-xs" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">API key (optional)</Label>
              <Input type="password" value={form.api_key} onChange={(e) => setForm((f) => ({ ...f, api_key: e.target.value }))} placeholder="sk-… (leave blank to keep stored)" className="font-mono text-xs" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Description / instructions</Label>
            <Textarea
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              placeholder="What this agent does and any privacy guidance."
              className="h-20 text-sm"
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs">Tools &amp; MCP servers</Label>
              <div className="flex gap-1.5">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => setForm((f) => ({ ...f, tools: [...f.tools, { name: "", kind: "function", server: "", description: "" }] }))}
                >
                  <Wrench className="size-3" /> Tool
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 text-xs"
                  onClick={() => setForm((f) => ({ ...f, tools: [...f.tools, { name: "", kind: "mcp", server: "", description: "" }] }))}
                >
                  <Plug className="size-3" /> MCP server
                </Button>
              </div>
            </div>
            {form.tools.length === 0 ? (
              <p className="text-[11px] text-muted-foreground">
                Tools and MCP servers the agent can call. Anything the agent forwards to them is treated as an external
                sink and scored as a potential leak.
              </p>
            ) : (
              <div className="space-y-2">
                {form.tools.map((t, idx) => (
                  <div key={idx} className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-2">
                    <Select
                      value={t.kind}
                      onValueChange={(v) =>
                        setForm((f) => ({ ...f, tools: f.tools.map((x, i) => (i === idx ? { ...x, kind: v as ToolConfig["kind"] } : x)) }))
                      }
                    >
                      <SelectTrigger className="h-8 w-28 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="function">Function</SelectItem>
                        <SelectItem value="mcp">MCP</SelectItem>
                      </SelectContent>
                    </Select>
                    <Input
                      value={t.name}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, tools: f.tools.map((x, i) => (i === idx ? { ...x, name: e.target.value } : x)) }))
                      }
                      placeholder={t.kind === "mcp" ? "tool (e.g. create_issue)" : "tool name (e.g. send_email)"}
                      className="h-8 flex-1 text-xs"
                    />
                    {t.kind === "mcp" && (
                      <Input
                        value={t.server ?? ""}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, tools: f.tools.map((x, i) => (i === idx ? { ...x, server: e.target.value } : x)) }))
                        }
                        placeholder="server (e.g. github-mcp)"
                        className="h-8 w-44 font-mono text-xs"
                      />
                    )}
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="size-7 text-sev-l4"
                      onClick={() => setForm((f) => ({ ...f, tools: f.tools.filter((_, i) => i !== idx) }))}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
          <p className="text-[11px] text-muted-foreground">
            A model + base URL lets AgentLeak execute this role in its scenario harness. Without one, the role produces
            a deterministic scripted trace. Neither option connects to a deployed application automatically.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={busy}>
              {busy && <Loader2 className="animate-spin" />} Save agent
            </Button>
          </div>
        </Card>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- Model
function ModelTab({ project }: { project: Project }) {
  const [model, setModel] = useState<ProjectModel | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    api.model(project.id).then(setModel).catch((e) => setError((e as Error).message))
  }, [project.id, project.config.agents])

  if (error) return <Card className="p-6 text-sm text-sev-l4">{error}</Card>
  if (!model) return <div className="text-sm text-muted-foreground">Loading…</div>
  return <ModelView model={model} />
}

// ---------------------------------------------------------------- Runs
function RunsTab({ projectId, runs, onChange }: { projectId: string; runs: RunSummary[]; onChange: () => void }) {
  const [pending, setPending] = useState<RunSummary | null>(null)

  if (!runs.length) {
    return (
      <Card className="p-8 text-sm text-muted-foreground">
        No runs in this project yet. Run a scenario from the <b>Test</b> tab, save an analysis from{" "}
        <Link className="underline underline-offset-2" to="/analyze">Analyze a trace</Link>, or submit traces with the SDK (<b>Integrate</b> tab).
      </Card>
    )
  }

  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-border bg-card">
        <RunsTable
          runs={runs}
          showProject={false}
          caption="Runs in this project"
          exportName={`runs-${projectId}`}
          extraColumns={[
            {
              id: "delete",
              header: "",
              value: () => "",
              sortable: false,
              exportable: false,
              cell: (r) => (
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7 text-muted-foreground hover:text-sev-l4"
                  aria-label={`Delete run ${r.id}`}
                  onClick={(e) => {
                    e.stopPropagation()
                    setPending(r)
                  }}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              ),
            },
          ]}
        />
      </div>
      <ProgressionView projectId={projectId} />
      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(v) => !v && setPending(null)}
        title={`Delete run ${pending?.id ?? ""}?`}
        description="The stored report is removed from this workspace. This cannot be undone."
        confirmLabel="Delete run"
        onConfirm={async () => {
          if (!pending) return
          try {
            await api.deleteRun(pending.id)
            toast.success(`Deleted ${pending.id}`)
            onChange()
          } catch (e) {
            toast.error((e as Error).message)
          }
        }}
      />
    </div>
  )
}

// ------------------------------------------------------------- Connect
function SnippetBlock({ title, snippet, note }: { title: string; snippet: string; note?: React.ReactNode }) {
  const [copied, setCopied] = useState(false)
  return (
    <Section
      title={title}
      description={note}
      actions={
        <Button
          variant="outline"
          size="sm"
          className="h-8"
          onClick={() =>
            navigator.clipboard
              .writeText(snippet)
              .then(() => {
                setCopied(true)
                toast.success("Copied")
                window.setTimeout(() => setCopied(false), 1500)
              })
              .catch(() => toast.error("Clipboard unavailable"))
          }
        >
          {copied ? <Check /> : <Copy />} Copy
        </Button>
      }
    >
      <pre className="overflow-x-auto px-4 py-3 font-mono text-[12px] leading-relaxed">{snippet}</pre>
    </Section>
  )
}

function ConnectTab({ project }: { project: Project }) {
  const [info, setInfo] = useState<ConnectInfo | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    api.connect(project.id).then(setInfo).catch((e) => setError((e as Error).message))
  }, [project.id, project.agent_type, project.name, project.config.agents])

  if (error)
    return (
      <p role="alert" className="rounded-lg border border-border p-4 text-sm text-sev-l4">
        Could not load the integration snippets: {error}
      </p>
    )
  if (!info) return <div className="h-40 rounded-lg bg-muted motion-safe:animate-pulse" aria-busy="true" aria-label="Loading snippets" />

  const blocks =
    info.agents.length > 0
      ? info.agents.map((a) => ({ key: a.id, title: `${a.name}, ${a.framework_label}`, snippet: a.snippet }))
      : [{ key: "single", title: `${agentLabel(project.agent_type)} agent`, snippet: info.snippet }]

  return (
    <div className="space-y-4">
      <p className="max-w-3xl text-[13px] text-muted-foreground">
        Instrument your own application. The SDK records the agent's events and submits each trace to this project;
        AgentLeak does not host or launch your agent. Runs appear under Runs once this server ({window.location.origin})
        receives them.
        {info.agents.length > 0 && " Each configured test agent has its own snippet."}
      </p>
      {blocks.map((b) => (
        <SnippetBlock key={b.key} title={`Capture traces: ${b.title}`} snippet={b.snippet} />
      ))}
      <SelfTestKeyPanel project={project} />
    </div>
  )
}

// --------------------------------------------------- Self-test API key
function SelfTestKeyPanel({ project }: { project: Project }) {
  const [key, setKey] = useState<string | null>(null)
  const [hasKey, setHasKey] = useState(false)
  const [reveal, setReveal] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [confirmRotate, setConfirmRotate] = useState(false)
  const origin = window.location.origin

  useEffect(() => {
    api
      .getApiKey(project.id)
      .then((r) => {
        setKey(r.api_key)
        setHasKey(r.has_key)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [project.id])

  async function generate() {
    setBusy(true)
    try {
      const r = await api.generateApiKey(project.id)
      setKey(r.api_key)
      setHasKey(true)
      setReveal(false)
      toast.success(hasKey ? "Key rotated; the previous key no longer works" : "Key generated")
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  // Snippets read the key from the environment: the key itself is never pasted into code.
  const curlSnippet = `curl -X POST ${origin}/api/selftest \\
  -H "Content-Type: application/json" \\
  -H "X-AgentLeak-Key: $AGENTLEAK_KEY" \\
  -d '{"trace": {"events": [...]}}'`
  const pySnippet = `import os, requests

resp = requests.post(
    "${origin}/api/selftest",
    headers={"X-AgentLeak-Key": os.environ["AGENTLEAK_KEY"]},
    json={"trace": trace},          # the trace your application captured
).json()

if not resp["passed"]:
    for hint in resp["remediation_hints"]:
        print(f"[{hint['priority']}] {hint['channel']}: {hint['data_types']}")
        print(hint["code_fix"])`

  return (
    <Section
      title="Project API key"
      description={
        <>
          Lets your application submit a trace it captured to <code className="font-mono">/api/selftest</code> without a
          browser session, and read back the result and fixes. Send it in the <code className="font-mono">X-AgentLeak-Key</code>{" "}
          header. Treat it as a secret.
        </>
      }
      actions={
        <Button variant="outline" size="sm" className="h-8" onClick={() => (hasKey ? setConfirmRotate(true) : generate())} disabled={busy || loading}>
          {busy ? <Loader2 className="animate-spin motion-reduce:animate-none" /> : <RefreshCw />}
          {hasKey ? "Rotate key" : "Generate key"}
        </Button>
      }
    >
      <div className="space-y-3 px-4 py-3">
        {loading ? (
          <p className="text-[13px] text-muted-foreground">Loading…</p>
        ) : hasKey && key ? (
          <div className="flex min-w-0 items-center gap-2">
            <code className="min-w-0 flex-1 truncate rounded-md border border-border bg-muted/50 px-3 py-1.5 font-mono text-[12px]" aria-label={reveal ? "Project API key" : "Project API key, masked"}>
              {reveal ? key : `${key.slice(0, 5)}${"•".repeat(16)}`}
            </code>
            <Button variant="outline" size="sm" className="h-8" onClick={() => setReveal((v) => !v)} aria-pressed={reveal}>
              {reveal ? <EyeOff /> : <Eye />} {reveal ? "Hide" : "Reveal"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-8"
              onClick={() => navigator.clipboard.writeText(key).then(() => toast.success("Key copied")).catch(() => toast.error("Clipboard unavailable"))}
            >
              <Copy /> Copy
            </Button>
          </div>
        ) : (
          <p className="text-[13px] text-muted-foreground">No key yet. Generate one to let your application submit traces.</p>
        )}
      </div>
      {hasKey && (
        <div className="space-y-3 border-t border-border px-4 py-3">
          <p className="text-[12px] text-muted-foreground">
            Export the key as <code className="font-mono">AGENTLEAK_KEY</code>, then:
          </p>
          <SnippetBlock title="Python" snippet={pySnippet} />
          <SnippetBlock title="curl" snippet={curlSnippet} />
          <p className="text-[12px] text-muted-foreground">
            The agent endpoints <code className="font-mono">/api/agent/register</code>, <code className="font-mono">/code</code>,{" "}
            <code className="font-mono">/improve</code> and <code className="font-mono">/status</code> take the same key; see the API reference.
          </p>
        </div>
      )}
      <ConfirmDialog
        open={confirmRotate}
        onOpenChange={setConfirmRotate}
        title="Rotate the project API key?"
        description="A new key is issued and the current one stops working at once. Update every application and CI job that uses it."
        confirmLabel="Rotate key"
        onConfirm={generate}
      />
    </Section>
  )
}

// ------------------------------------------------------------ Settings
type Gate = { enabled: boolean; maxRi: string; maxFindings: string; forbidLevels: number[]; forbidChannels: string[] }

function gateFrom(p: Record<string, unknown> | undefined): Gate {
  const policy = (p ?? {}) as { max_risk_index?: number | null; max_findings?: number | null; forbid_levels?: number[]; forbid_channels?: string[] }
  return {
    enabled: !!p && Object.keys(p).length > 0,
    maxRi: policy.max_risk_index != null ? String(policy.max_risk_index) : "",
    maxFindings: policy.max_findings != null ? String(policy.max_findings) : "",
    forbidLevels: policy.forbid_levels ?? [],
    forbidChannels: policy.forbid_channels ?? [],
  }
}

/** The gate as config, or a message saying what is wrong with it. */
export function gateToPolicy(g: Gate, existing?: Record<string, unknown>): { policy: Record<string, unknown> | null; error?: string } {
  if (!g.enabled) return { policy: null }
  const out: Record<string, unknown> = { ...(existing ?? {}) }
  if (g.maxRi.trim()) {
    const v = Number(g.maxRi)
    if (!(v >= 0 && v <= 1)) return { policy: null, error: "Maximum RI must be between 0 and 1." }
    out.max_risk_index = v
  } else delete out.max_risk_index
  if (g.maxFindings.trim()) {
    const v = Number(g.maxFindings)
    if (!Number.isInteger(v) || v < 0) return { policy: null, error: "Maximum findings must be a whole number, 0 or more." }
    out.max_findings = v
  } else delete out.max_findings
  out.forbid_levels = g.forbidLevels
  out.forbid_channels = g.forbidChannels
  return { policy: out }
}

function SettingsTab({ project, onSaved, onDeleted }: { project: Project; onSaved: () => void; onDeleted: () => void }) {
  const agentTypes = useAgentTypes()
  const meta = useMeta()
  const emissions = channelSplit(meta).emissions
  const uid = useId()
  const f = (k: string) => `${uid}-${k}`
  const [name, setName] = useState(project.name)
  const [description, setDescription] = useState(project.description ?? "")
  const [agentType, setAgentType] = useState(project.agent_type)
  const [detectors, setDetectors] = useState<Record<string, boolean>>({
    pii: true, secrets: true, healthcare: true, finance: false, hr: false,
    ...(project.config.detectors ?? {}),
  })
  const [redact, setRedact] = useState(project.config.redact ?? true)
  const [vaultMode, setVaultMode] = useState<"observed" | "explicit">(project.config.vault?.mode ?? "observed")
  const [vault, setVault] = useState<Record<string, number>>({ 1: 0, 2: 0, 3: 0, 4: 0, ...(project.config.vault?.levels ?? {}) })
  const [rules, setRules] = useState<CustomRule[]>(project.config.custom_detectors ?? [])
  const existingPolicy = (project.config as { privacy_policy?: Record<string, unknown> }).privacy_policy
  const [gate, setGate] = useState<Gate>(gateFrom(existingPolicy))
  const [agentBaseUrl, setAgentBaseUrl] = useState(project.config.agent?.base_url ?? "")
  const [agentModel, setAgentModel] = useState(project.config.agent?.model ?? "")
  const [agentKey, setAgentKey] = useState("")
  const agentKeySet = project.config.agent?.api_key_set ?? false
  const [busy, setBusy] = useState(false)
  const [formError, setFormError] = useState("")
  const [confirmDelete, setConfirmDelete] = useState(false)

  async function save(e: React.FormEvent) {
    e.preventDefault()
    const { policy, error } = gateToPolicy(gate, existingPolicy)
    if (error) {
      setFormError(error)
      return
    }
    setFormError("")
    setBusy(true)
    try {
      // PATCH replaces the whole config. Start from the stored config, read
      // just now, so keys this form does not show (test agents, the project
      // API key, detection tier) survive a save.
      const fresh = await api.project(project.id)
      const base: Record<string, unknown> = { ...fresh.config }
      const config: Record<string, unknown> = {
        ...base,
        detectors,
        redact,
        vault: vaultMode === "explicit" ? { mode: "explicit", levels: vault } : { mode: "observed" },
        custom_detectors: rules.filter((r) => r.name && r.pattern).map((r) => ({ ...r, data_type: r.name })),
        // A blank key keeps the stored one (the server restores it).
        agent: { base_url: agentBaseUrl.trim(), model: agentModel.trim(), api_key: agentKey },
      }
      if (policy) config.privacy_policy = policy
      else delete config.privacy_policy
      await api.updateProject(project.id, { name, description, agent_type: agentType, config })
      setAgentKey("")
      toast.success("Project saved")
      onSaved()
    } catch (err) {
      setFormError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    try {
      await api.deleteProject(project.id)
      toast.success(`Deleted ${project.name}`)
      onDeleted()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const presets = [
    { label: "OpenAI", url: "https://api.openai.com/v1", model: "gpt-4o-mini" },
    { label: "OpenRouter", url: "https://openrouter.ai/api/v1", model: "openai/gpt-4o-mini" },
    { label: "Ollama, local", url: "http://localhost:11434/v1", model: "llama3.1" },
  ]

  return (
    <form onSubmit={save} className="max-w-4xl space-y-4" noValidate>
      <Section title="Project">
        <FieldRow label="Name" htmlFor={f("name")}>
          <Input id={f("name")} value={name} onChange={(e) => setName(e.target.value)} maxLength={200} className="h-8 text-[13px]" />
        </FieldRow>
        <FieldRow label="Description" htmlFor={f("desc")} help="Optional.">
          <Input id={f("desc")} value={description} onChange={(e) => setDescription(e.target.value)} maxLength={500} className="h-8 text-[13px]" />
        </FieldRow>
        <FieldRow label="Agent framework" htmlFor={f("fw")} help="Chooses the SDK snippet on Integrate.">
          <select id={f("fw")} value={agentType} onChange={(e) => setAgentType(e.target.value)} className={`${inputSm} w-full sm:w-auto`}>
            {agentTypes.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
        </FieldRow>
      </Section>

      <Section title="Detection" description="Applied to every run stored in this project. Detectors are deterministic patterns and dictionaries.">
        <FieldRow label="Detectors">
          <div className="grid gap-x-6 gap-y-2 sm:grid-cols-3">
            {DETECTORS.map((d) => (
              <label key={d} className="flex items-center gap-2 text-[13px]">
                <Switch checked={!!detectors[d]} onCheckedChange={(v) => setDetectors((s) => ({ ...s, [d]: v }))} aria-label={DETECTOR_LABEL[d]} />
                {DETECTOR_LABEL[d]}
                <span className="text-[11px] text-muted-foreground">{detectors[d] ? "on" : "off"}</span>
              </label>
            ))}
          </div>
        </FieldRow>
        <FieldRow label="Mask values in reports" help="Off stores raw values in this project's reports. Keep it on unless you need them.">
          <label className="flex items-center gap-2 text-[13px]">
            <Switch checked={redact} onCheckedChange={setRedact} aria-label="Mask values in reports" />
            {redact ? "Masked" : "Raw values stored"}
          </label>
        </FieldRow>
        <FieldRow label="Custom rules" help="A name and a regular expression. Patterns with nested repetition are refused.">
          <div className="space-y-2">
            {rules.length === 0 && <p className="text-[13px] text-muted-foreground">No custom rule.</p>}
            {rules.map((r, i) => (
              <div key={i} className="flex min-w-0 gap-2">
                <Input
                  aria-label={`Rule ${i + 1} name`}
                  value={r.name}
                  placeholder="name"
                  className="h-8 w-36 text-[13px]"
                  onChange={(e) => setRules((s) => s.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
                />
                <Input
                  aria-label={`Rule ${i + 1} pattern`}
                  value={r.pattern}
                  placeholder="regular expression"
                  className="h-8 min-w-0 flex-1 font-mono text-[12px]"
                  onChange={(e) => setRules((s) => s.map((x, j) => (j === i ? { ...x, pattern: e.target.value } : x)))}
                />
                <Button type="button" variant="ghost" size="sm" className="h-8 shrink-0" aria-label={`Remove rule ${i + 1}`} onClick={() => setRules((s) => s.filter((_, j) => j !== i))}>
                  <Trash2 />
                </Button>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" className="h-8" onClick={() => setRules((r) => [...r, { name: "", pattern: "", severity: "high", data_type: "" }])}>
              <Plus /> Add rule
            </Button>
          </div>
        </FieldRow>
      </Section>

      <Section title="Vault scope (ρ_S)" description="The denominator of the Risk Index.">
        <FieldRow label="Scope">
          <fieldset className="space-y-1.5 text-[13px]">
            <legend className="sr-only">Vault scope</legend>
            <label className="flex items-start gap-2">
              <input type="radio" name={f("vault")} checked={vaultMode === "observed"} onChange={() => setVaultMode("observed")} className="mt-1 accent-foreground" />
              <span>
                Observed. <span className="text-muted-foreground">Every distinct value detected in the trace; the denominator can differ from run to run.</span>
              </span>
            </label>
            <label className="flex items-start gap-2">
              <input type="radio" name={f("vault")} checked={vaultMode === "explicit"} onChange={() => setVaultMode("explicit")} className="mt-1 accent-foreground" />
              <span>
                Explicit. <span className="text-muted-foreground">The secrets the agent can reach, counted per level: a stable denominator for comparing releases.</span>
              </span>
            </label>
          </fieldset>
          {vaultMode === "explicit" && (
            <div className="mt-2 flex flex-wrap gap-3">
              {([4, 3, 2, 1] as const).map((l) => (
                <label key={l} className="flex items-center gap-1.5 text-[12px]">
                  <span className="font-mono">L{l}</span>
                  <Input type="number" min={0} value={vault[l]} className="h-8 w-20 text-[13px] tnum" onChange={(e) => setVault((v) => ({ ...v, [l]: Math.max(0, Math.floor(+e.target.value || 0)) }))} />
                </label>
              ))}
            </div>
          )}
        </FieldRow>
      </Section>

      <Section
        title="Evaluation gate"
        description="Marks a run blocked when one of these limits is crossed. It applies to every run stored in this project; a gate sent with a run is used only when the project has none."
      >
        <FieldRow label="Gate">
          <label className="flex items-center gap-2 text-[13px]">
            <Switch checked={gate.enabled} onCheckedChange={(v) => setGate((g) => ({ ...g, enabled: v }))} aria-label="Evaluation gate" />
            {gate.enabled ? "On" : "Off: runs are scored but never blocked by a project gate"}
          </label>
        </FieldRow>
        {gate.enabled && (
          <>
            <FieldRow label="Maximum Risk Index" htmlFor={f("maxri")} help="0 to 1. Empty: no limit.">
              <Input id={f("maxri")} inputMode="decimal" value={gate.maxRi} onChange={(e) => setGate((g) => ({ ...g, maxRi: e.target.value }))} placeholder="for example 0.2" className="h-8 w-32 font-mono text-[13px]" />
            </FieldRow>
            <FieldRow label="Maximum findings" htmlFor={f("maxf")} help="Leaked findings per run. Empty: no limit.">
              <Input id={f("maxf")} inputMode="numeric" value={gate.maxFindings} onChange={(e) => setGate((g) => ({ ...g, maxFindings: e.target.value }))} placeholder="for example 0" className="h-8 w-32 font-mono text-[13px]" />
            </FieldRow>
            <FieldRow label="Block any finding at level">
              <div className="flex flex-wrap gap-3 text-[13px]">
                {[4, 3, 2, 1].map((l) => (
                  <label key={l} className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      className="accent-foreground"
                      checked={gate.forbidLevels.includes(l)}
                      onChange={(e) => setGate((g) => ({ ...g, forbidLevels: e.target.checked ? [...g.forbidLevels, l].sort() : g.forbidLevels.filter((x) => x !== l) }))}
                    />
                    <span className="font-mono">L{l}</span>
                  </label>
                ))}
              </div>
            </FieldRow>
            <FieldRow label="Block any finding on channel">
              <div className="flex flex-wrap gap-x-4 gap-y-2 text-[13px]">
                {emissions.map((c) => (
                  <label key={c} className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      className="accent-foreground"
                      checked={gate.forbidChannels.includes(c)}
                      onChange={(e) => setGate((g) => ({ ...g, forbidChannels: e.target.checked ? [...g.forbidChannels, c] : g.forbidChannels.filter((x) => x !== c) }))}
                    />
                    <code className="font-mono text-[12px]">{c}</code>
                  </label>
                ))}
              </div>
            </FieldRow>
          </>
        )}
      </Section>

      <Section title="Scenario model endpoint" description="Any OpenAI-compatible endpoint. Used only when this project runs a scenario live; analysis itself never calls a model.">
        <FieldRow label="Presets">
          <div className="flex flex-wrap gap-1.5">
            {presets.map((p) => (
              <Button
                key={p.label}
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-[12px]"
                onClick={() => {
                  setAgentBaseUrl(p.url)
                  if (!agentModel) setAgentModel(p.model)
                }}
              >
                {p.label}
              </Button>
            ))}
          </div>
        </FieldRow>
        <FieldRow label="Base URL" htmlFor={f("url")}>
          <Input id={f("url")} value={agentBaseUrl} onChange={(e) => setAgentBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1" className="h-8 font-mono text-[12px]" />
        </FieldRow>
        <FieldRow label="Model" htmlFor={f("model")}>
          <Input id={f("model")} value={agentModel} onChange={(e) => setAgentModel(e.target.value)} placeholder="gpt-4o-mini" className="h-8 font-mono text-[12px]" />
        </FieldRow>
        <FieldRow label="API key" htmlFor={f("key")} help={agentKeySet ? "A key is stored. Leave empty to keep it." : "Stored on this server, never returned by the API. Empty: use OPENAI_API_KEY or OPENROUTER_API_KEY from the environment."}>
          <Input id={f("key")} type="password" autoComplete="off" value={agentKey} onChange={(e) => setAgentKey(e.target.value)} placeholder={agentKeySet ? "stored" : "not set"} className="h-8 font-mono text-[12px]" />
        </FieldRow>
      </Section>

      {formError && (
        <p role="alert" className="text-[13px] text-sev-l4">
          {formError}
        </p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Button type="button" variant="ghost" className="text-sev-l4 hover:text-sev-l4" onClick={() => setConfirmDelete(true)}>
          <Trash2 /> Delete project
        </Button>
        <Button type="submit" disabled={busy}>
          {busy && <Loader2 className="animate-spin motion-reduce:animate-none" />} Save changes
        </Button>
      </div>
      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`Delete project ${project.name}?`}
        description={`Its ${project.run_count ?? 0} run(s), code scans, triage decisions and API key are removed. This cannot be undone.`}
        confirmLabel="Delete project"
        onConfirm={remove}
      />
    </form>
  )
}
