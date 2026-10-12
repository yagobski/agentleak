// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useCallback, useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { Bot, Check, Copy, Eye, EyeOff, KeyRound, Loader2, Pencil, Play, Plug, Plus, RefreshCw, Shield, Sparkles, Trash2, Wrench, X } from "lucide-react"
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
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Textarea } from "@/components/ui/textarea"
import { ModelView } from "@/features/ModelView"
import { AgentCardView } from "@/features/AgentCardView"
import { ProgressionView } from "@/features/ProgressionView"
import { RedTeamView } from "@/features/RedTeamView"
import { RunRow } from "@/features/RunRow"

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

  const reload = useCallback(() => {
    api.project(id).then(setProject).catch(() => setNotFound(true))
    api.projectRuns(id).then(setRuns).catch(() => {})
  }, [id])
  useEffect(reload, [reload])

  if (notFound) return <div className="animate-fade-up text-sm text-sev-l4">Project not found.</div>
  if (!project) return <div className="animate-fade-up text-sm text-muted-foreground">Loading…</div>

  return (
    <div className="animate-fade-up">
      <div className="mb-5">
        <Link to="/projects" className="text-xs text-muted-foreground hover:text-foreground">
          ← Projects
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight">{project.name}</h1>
          <span className="rounded bg-muted px-2 py-0.5 text-[11px] uppercase tracking-wide text-muted-foreground">
            {agentLabel(project.agent_type)}
          </span>
          <span className="text-sm text-muted-foreground">
            {project.run_count ?? 0} runs
            {project.avg_risk_index != null ? ` · avg RI ${project.avg_risk_index.toFixed(3)}` : ""}
          </span>
        </div>
        {project.description && <p className="mt-1 text-sm text-muted-foreground">{project.description}</p>}
      </div>

      <Tabs defaultValue="audit">
        <TabsList className="h-auto max-w-full justify-start overflow-x-auto">
          <TabsTrigger value="audit">Test</TabsTrigger>
          <TabsTrigger value="card" className="flex items-center gap-1.5">
            <Bot className="h-3.5 w-3.5 text-primary" />
            Identity &amp; code
          </TabsTrigger>
          <TabsTrigger value="agents">Test agents ({project.config.agents?.length ?? 0})</TabsTrigger>
          <TabsTrigger value="model">System map</TabsTrigger>
          <TabsTrigger value="runs">Evidence ({runs.length})</TabsTrigger>
          <TabsTrigger value="redteam" className="flex items-center gap-1.5">
            <Shield className="h-3.5 w-3.5 text-red-500" />
            Adversarial
          </TabsTrigger>
          <TabsTrigger value="connect">Integrate</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

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
                <Sparkles className="size-3.5 text-primary" />
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
  const nav = useNavigate()

  if (!runs.length) {
    return (
      <Card className="p-10 text-center text-sm text-muted-foreground">
        No evidence yet. Analyze a captured trace, run a controlled scenario, or integrate the SDK.
      </Card>
    )
  }

  return (
    <div className="space-y-5">
      {/* Score progression + run-to-run comparison */}
      <ProgressionView projectId={projectId} />

      {/* Full run list */}
      <Card>
        <div className="border-b border-border px-5 py-2.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          All runs ({runs.length})
        </div>
        <div className="divide-y divide-border">
          {runs.map((r) => (
            <RunRow
              key={r.id}
              run={r}
              onClick={() => nav(`/runs/${r.id}`)}
              right={
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7 text-muted-foreground"
                  onClick={(e) => {
                    e.stopPropagation()
                    api.deleteRun(r.id).then(() => {
                      toast.success("Run deleted")
                      onChange()
                    })
                  }}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              }
            />
          ))}
        </div>
      </Card>
    </div>
  )
}

// ------------------------------------------------------------- Connect
function ConnectTab({ project }: { project: Project }) {
  const [copied, setCopied] = useState("")
  const [info, setInfo] = useState<ConnectInfo | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    api.connect(project.id).then(setInfo).catch((e) => setError((e as Error).message))
  }, [project.id, project.agent_type, project.name, project.config.agents])

  function copy(key: string, text: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(key)
      toast.success("Snippet copied")
      setTimeout(() => setCopied(""), 1500)
    })
  }

  if (error) return <Card className="p-6 text-sm text-sev-l4">{error}</Card>
  if (!info) return <div className="text-sm text-muted-foreground">Loading…</div>

  const blocks =
    info.agents.length > 0
      ? info.agents.map((a) => ({ key: a.id, title: `${a.name} · ${a.framework_label}`, snippet: a.snippet }))
      : [{ key: "single", title: `${agentLabel(project.agent_type)} agent`, snippet: info.snippet }]

  return (
    <div className="space-y-4">
      <div className="rounded-md border border-primary/20 bg-primary/[0.03] px-4 py-3 text-sm text-muted-foreground">
        Instrument your real application here. The SDK records execution events and submits traces to this project;
        AgentLeak never needs to host or launch your agent.
      </div>
      {info.agents.length > 0 && (
        <p className="text-sm text-muted-foreground">
          Connect each agent of your system with its framework's SDK. Runs submitted by any agent appear under this
          project.
        </p>
      )}
      {blocks.map((b) => (
        <Card key={b.key}>
          <div className="flex items-center justify-between border-b border-border px-5 py-3">
            <div className="text-sm">
              Capture <b>{b.title}</b> traces via the SDK
            </div>
            <Button variant="outline" size="sm" onClick={() => copy(b.key, b.snippet)}>
              {copied === b.key ? <Check /> : <Copy />} Copy
            </Button>
          </div>
          <pre className="overflow-x-auto p-5 font-mono text-[12px] leading-relaxed text-foreground/90">{b.snippet}</pre>
        </Card>
      ))}
      <SelfTestKeyPanel project={project} />
      <div className="rounded-md border border-border px-5 py-3 text-xs text-muted-foreground">
        Make sure the platform is running (<code className="rounded bg-muted px-1.5 py-0.5">agentleak serve</code>).
        Submitted runs appear under this project.
      </div>
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
  const [copied, setCopied] = useState("")

  useEffect(() => {
    api.getApiKey(project.id)
      .then((r) => { setKey(r.api_key); setHasKey(r.has_key) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [project.id])

  async function generate() {
    setBusy(true)
    try {
      const r = await api.generateApiKey(project.id)
      setKey(r.api_key)
      setHasKey(true)
      setReveal(true)
      toast.success(hasKey ? "API key rotated" : "API key generated")
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function copy(id: string, text: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(id)
      toast.success("Copied")
      setTimeout(() => setCopied(""), 1500)
    })
  }

  const displayKey = key ? (reveal ? key : `${key.slice(0, 6)}${"•".repeat(20)}`) : ""
  const curlSnippet = `curl -X POST http://127.0.0.1:8000/api/selftest \\
  -H "Content-Type: application/json" \\
  -d '{
    "api_key": "${key ?? "ak_…"}",
    "trace": { /* your captured agent trace */ },
    "scenario_id": "healthcare_patient_summary"
  }'`

  const pySnippet = `import os, requests

# Submit a trace captured by the application and read back fixes.
resp = requests.post(
    "http://127.0.0.1:8000/api/selftest",
    json={
        "api_key": os.environ["AGENTLEAK_KEY"],   # ${key ?? "ak_…"}
        "trace": trace,                            # captured this run
        "scenario_id": "healthcare_patient_summary",
    },
).json()

# 1. Regulatory verdict — is the agent allowed to ship?
if not resp["compliant"]:
    print("Blocked by:", ", ".join(resp["failed_frameworks"]))  # e.g. hipaa, gdpr

# 2. Pull back machine-readable code fixes and apply them.
if not resp["passed"]:
    for hint in resp["remediation_hints"]:
        print(f"[{hint['priority']}] {hint['channel']} leaks {hint['data_types']}")
        print(hint["code_fix"])      # apply this patch, then re-run`

  const loopSnippet = `from agentleak import AgentSelfClient

me = AgentSelfClient(api_key=os.environ["AGENTLEAK_KEY"])

# 1. Register identity (A2A/Nasiko AgentCard) + code source
me.register(card={
    "name": "${project.name}",
    "capabilities": ["..."],
    "source": {"type": "github", "repo": "owner/repo"},
})
me.scan_code()                      # static scan of the declared repo

# 2. Improvement loop: test → read next_steps → fix → re-test
step = me.improve(trace)
while not step["passed"]:
    for todo in step["next_steps"]:  # priority-sorted, machine-actionable
        apply_fix(todo)
    step = me.improve(new_trace())

print(me.status()["progression"])    # score delta across all runs`

  return (
    <Card className="border-primary/25">
      <div className="flex items-center justify-between border-b border-border px-5 py-3">
        <div className="flex items-center gap-2 text-sm">
          <KeyRound className="size-4 text-primary" />
          <b>Let your agent submit its own traces</b>
        </div>
        <Button variant="outline" size="sm" onClick={generate} disabled={busy}>
          {busy ? <Loader2 className="animate-spin" /> : <RefreshCw />}
          {hasKey ? "Rotate key" : "Generate key"}
        </Button>
      </div>
      <div className="space-y-4 p-5">
        <p className="text-sm text-muted-foreground">
          Issue a project API key so your application can POST a trace it already captured to{" "}
          <code className="rounded bg-muted px-1.5 py-0.5 text-primary">/api/selftest</code>, get scored, and pull
          back structured code fixes it may apply. AgentLeak analyzes the submitted evidence; it does not launch the agent.
        </p>

        {loading ? (
          <div className="text-sm text-muted-foreground">Loading…</div>
        ) : hasKey && key ? (
          <div className="flex items-center gap-2">
            <code className="flex-1 truncate rounded-md border border-border bg-muted/60 px-3 py-2 font-mono text-[12px]">
              {displayKey}
            </code>
            <Button variant="outline" size="icon" onClick={() => setReveal((v) => !v)} title={reveal ? "Hide" : "Reveal"}>
              {reveal ? <EyeOff /> : <Eye />}
            </Button>
            <Button variant="outline" size="icon" onClick={() => copy("key", key)} title="Copy key">
              {copied === "key" ? <Check /> : <Copy />}
            </Button>
          </div>
        ) : (
          <div className="rounded-md border border-dashed border-border px-4 py-3 text-sm text-muted-foreground">
            No API key yet. Generate one to enable authenticated trace submission.
          </div>
        )}

        {hasKey && key && (
          <>
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                  Python — submit, score &amp; auto-fix
                </span>
                <Button variant="ghost" size="sm" onClick={() => copy("py", pySnippet)}>
                  {copied === "py" ? <Check /> : <Copy />} Copy
                </Button>
              </div>
              <pre className="overflow-x-auto rounded-md border border-border bg-muted/60 p-4 font-mono text-[12px] leading-relaxed">{pySnippet}</pre>
            </div>
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                  curl
                </span>
                <Button variant="ghost" size="sm" onClick={() => copy("curl", curlSnippet)}>
                  {copied === "curl" ? <Check /> : <Copy />} Copy
                </Button>
              </div>
              <pre className="overflow-x-auto rounded-md border border-border bg-muted/60 p-4 font-mono text-[12px] leading-relaxed">{curlSnippet}</pre>
            </div>
            <div>
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                  Python — autonomous improvement loop
                </span>
                <Button variant="ghost" size="sm" onClick={() => copy("loop", loopSnippet)}>
                  {copied === "loop" ? <Check /> : <Copy />} Copy
                </Button>
              </div>
              <pre className="overflow-x-auto rounded-md border border-border bg-muted/60 p-4 font-mono text-[12px] leading-relaxed">{loopSnippet}</pre>
              <div className="mt-2 grid gap-1 text-[11px] text-muted-foreground sm:grid-cols-2">
                <span><code className="rounded bg-muted px-1 py-0.5">POST /api/agent/register</code> — upsert the agent card</span>
                <span><code className="rounded bg-muted px-1 py-0.5">POST /api/agent/code</code> — static-scan its own source</span>
                <span><code className="rounded bg-muted px-1 py-0.5">POST /api/agent/improve</code> — test + delta + next steps</span>
                <span><code className="rounded bg-muted px-1 py-0.5">GET /api/agent/status</code> — progression &amp; compliance posture</span>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              The key authenticates as <code className="rounded bg-muted px-1.5 py-0.5">api_key</code> in the body or the{" "}
              <code className="rounded bg-muted px-1.5 py-0.5">X-AgentLeak-Key</code> header. Treat it like a secret.
            </p>
          </>
        )}
      </div>
    </Card>
  )
}

// ------------------------------------------------------------ Settings
function SettingsTab({ project, onSaved, onDeleted }: { project: Project; onSaved: () => void; onDeleted: () => void }) {
  const agentTypes = useAgentTypes()
  const [name, setName] = useState(project.name)
  const [agentType, setAgentType] = useState(project.agent_type)
  const [detectors, setDetectors] = useState<Record<string, boolean>>({
    pii: true, secrets: true, healthcare: true, finance: false, hr: false,
    ...(project.config.detectors ?? {}),
  })
  const [redact, setRedact] = useState(project.config.redact ?? true)
  const [vaultMode, setVaultMode] = useState<"observed" | "explicit">(project.config.vault?.mode ?? "observed")
  const [vault, setVault] = useState<Record<string, number>>({
    1: 0, 2: 0, 3: 0, 4: 0, ...(project.config.vault?.levels ?? {}),
  })
  const [rules, setRules] = useState<CustomRule[]>(project.config.custom_detectors ?? [])
  const [agentBaseUrl, setAgentBaseUrl] = useState(project.config.agent?.base_url ?? "")
  const [agentModel, setAgentModel] = useState(project.config.agent?.model ?? "")
  const [agentKey, setAgentKey] = useState("")
  const agentKeySet = project.config.agent?.api_key_set ?? false
  const [busy, setBusy] = useState(false)

  async function save() {
    setBusy(true)
    try {
      const config = {
        detectors,
        redact,
        vault: vaultMode === "explicit" ? { mode: "explicit", levels: vault } : { mode: "observed" },
        custom_detectors: rules.filter((r) => r.name && r.pattern).map((r) => ({ ...r, data_type: r.name })),
        // Blank api_key is preserved server-side (the stored key is kept).
        agent: { base_url: agentBaseUrl.trim(), model: agentModel.trim(), api_key: agentKey },
      }
      await api.updateProject(project.id, { name, agent_type: agentType, config })
      toast.success("Project saved")
      onSaved()
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!confirm(`Delete project “${project.name}” and all its runs?`)) return
    try {
      await api.deleteProject(project.id)
      toast.success("Project deleted")
      onDeleted()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="space-y-4 p-5">
        <div className="space-y-1.5">
          <Label className="text-xs">Name</Label>
          <Input value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="space-y-1.5">
          <Label className="text-xs">Agent framework</Label>
          <Select value={agentType} onValueChange={setAgentType}>
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
        <Separator />
        <div className="flex items-center justify-between">
          <span className="text-sm">Redact sensitive values</span>
          <Switch checked={redact} onCheckedChange={setRedact} />
        </div>
        <div className="space-y-2">
          <Label className="text-xs">Vault scope (ρ_S)</Label>
          <div className="grid grid-cols-2 gap-1.5 rounded-md bg-muted p-1">
            {(["observed", "explicit"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setVaultMode(m)}
                className={`rounded px-2 py-1 text-xs font-medium capitalize transition-colors ${vaultMode === m ? "bg-background text-foreground shadow-sm" : "text-muted-foreground"}`}
              >
                {m === "observed" ? "Observed (auto)" : "Explicit"}
              </button>
            ))}
          </div>
          {vaultMode === "explicit" && (
            <div className="grid grid-cols-4 gap-1.5">
              {([4, 3, 2, 1] as const).map((l) => (
                <div key={l}>
                  <Label className="mb-1 block text-center text-[11px] text-muted-foreground">L{l}</Label>
                  <Input
                    type="number"
                    min={0}
                    value={vault[l]}
                    className="h-8 text-center text-xs"
                    onChange={(e) => setVault((v) => ({ ...v, [l]: Math.max(0, +e.target.value) }))}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>

      <Card className="space-y-4 p-5">
        <div className="space-y-3">
          <Label className="text-xs">Detectors</Label>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2.5">
            {DETECTORS.map((d) => (
              <div key={d} className="flex items-center justify-between">
                <span className="text-sm">{DETECTOR_LABEL[d]}</span>
                <Switch checked={detectors[d]} onCheckedChange={(v) => setDetectors((s) => ({ ...s, [d]: v }))} />
              </div>
            ))}
          </div>
        </div>
        <Separator />
        <div className="space-y-2.5">
          <div className="flex items-center justify-between">
            <Label className="text-xs">Custom rules</Label>
            <button
              onClick={() => setRules((r) => [...r, { name: "", pattern: "", severity: "high", data_type: "" }])}
              className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
            >
              <Plus className="size-3" /> Add
            </button>
          </div>
          {rules.map((r, i) => (
            <div key={i} className="flex gap-1.5">
              <Input
                value={r.name}
                placeholder="name"
                className="h-7 text-xs"
                onChange={(e) => setRules((s) => s.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
              />
              <Input
                value={r.pattern}
                placeholder="regex"
                className="h-7 flex-[2] font-mono text-xs"
                onChange={(e) => setRules((s) => s.map((x, j) => (j === i ? { ...x, pattern: e.target.value } : x)))}
              />
              <Button variant="ghost" size="icon" className="size-7 shrink-0" onClick={() => setRules((s) => s.filter((_, j) => j !== i))}>
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          ))}
        </div>
      </Card>

      <Card className="space-y-4 p-5 lg:col-span-2">
        <div className="flex items-center gap-2">
          <Bot className="size-4 text-primary" />
          <Label className="text-xs">Scenario model endpoint</Label>
          <span className="text-[11px] text-muted-foreground">
            OpenAI-compatible (OpenAI, OpenRouter, Ollama, vLLM…). Used only by the AgentLeak scenario harness.
          </span>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {[
            { label: "OpenAI", url: "https://api.openai.com/v1", model: "gpt-4o-mini" },
            { label: "OpenRouter", url: "https://openrouter.ai/api/v1", model: "openai/gpt-4o-mini" },
            { label: "Ollama", url: "http://localhost:11434/v1", model: "llama3.1" },
          ].map((p) => (
            <button
              key={p.label}
              onClick={() => { setAgentBaseUrl(p.url); if (!agentModel) setAgentModel(p.model) }}
              className="rounded-full border border-border px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground"
            >
              {p.label}
            </button>
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label className="text-xs">Base URL</Label>
            <Input value={agentBaseUrl} onChange={(e) => setAgentBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1" className="font-mono text-xs" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">Model</Label>
            <Input value={agentModel} onChange={(e) => setAgentModel(e.target.value)} placeholder="gpt-4o-mini" className="font-mono text-xs" />
          </div>
          <div className="space-y-1.5">
            <Label className="text-xs">API key</Label>
            <Input
              type="password"
              value={agentKey}
              onChange={(e) => setAgentKey(e.target.value)}
              placeholder={agentKeySet ? "•••••••• (stored — leave blank to keep)" : "sk-… (or set via env var)"}
              className="font-mono text-xs"
            />
          </div>
        </div>
        <p className="text-[11px] text-muted-foreground">
          The key is stored locally and never returned by the API. You can also leave it blank and export
          <code className="mx-1 rounded bg-muted px-1 py-0.5">OPENAI_API_KEY</code>/
          <code className="rounded bg-muted px-1 py-0.5">OPENROUTER_API_KEY</code> before launching.
        </p>
      </Card>

      <div className="lg:col-span-2 flex items-center justify-between">
        <Button variant="ghost" className="text-sev-l4" onClick={remove}>
          <Trash2 /> Delete project
        </Button>
        <Button onClick={save} disabled={busy}>
          {busy && <Loader2 className="animate-spin" />} Save changes
        </Button>
      </div>
    </div>
  )
}
