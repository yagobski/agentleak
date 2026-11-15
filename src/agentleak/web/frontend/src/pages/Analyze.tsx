// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useCallback, useEffect, useRef, useState, type DragEvent } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { ChevronRight, FileUp, Loader2, Play, Save } from "lucide-react"
import { toast } from "sonner"
import { api, type Project, type Report, type Scenario, type TraceDoc } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { AnalysisOptions, DEFAULT_OPTIONS, optionsSummary, optionsToPayload, type OptionsState } from "@/features/AnalysisOptions"
import { ResultSkeleton, ResultsView } from "@/features/ResultsView"
import { PageHeader } from "@/layout/AppShell"

type Mode = "scenario" | "file" | "paste"
type AnalysisInput =
  | { kind: "scenario"; id: string }
  | { kind: "trace"; trace: unknown; label: string }

const SESSION_KEY = "agentleak-analyze-last"

interface Saved {
  report: Report
  label: string
  scenarioId?: string
}

function readSaved(): Saved | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    return raw ? (JSON.parse(raw) as Saved) : null
  } catch {
    return null
  }
}

function scenarioLabel(s: Scenario) {
  return s.name && s.name !== s.id ? s.name : s.id
}

export function Analyze() {
  const [params, setParams] = useSearchParams()
  const nav = useNavigate()
  const urlScenario = params.get("scenario")
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [mode, setMode] = useState<Mode>("scenario")
  const [scenarioId, setScenarioId] = useState(urlScenario ?? "")
  const [pasted, setPasted] = useState("")
  const [file, setFile] = useState<{ name: string; trace: unknown; events: number | null } | null>(null)
  const [options, setOptions] = useState<OptionsState>(DEFAULT_OPTIONS)
  const [showOptions, setShowOptions] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [dragging, setDragging] = useState(false)
  const [saved] = useState(readSaved)
  const [report, setReport] = useState<Report | null>(saved?.report ?? null)
  const [resultLabel, setResultLabel] = useState(saved?.label ?? "")
  const [trace, setTrace] = useState<TraceDoc | null>(null)
  const [lastInput, setLastInput] = useState<AnalysisInput | null>(saved?.scenarioId ? { kind: "scenario", id: saved.scenarioId } : null)
  const [editing, setEditing] = useState(!saved)
  const [saveOpen, setSaveOpen] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api
      .scenarios()
      .then((list) => {
        setScenarios(list)
        setScenarioId((cur) => cur || list.find((s) => s.source === "builtin" && s.expected_outcome === "leak")?.id || list[0]?.id || "")
      })
      .catch((e) => setError(`Could not load scenarios: ${(e as Error).message}`))
  }, [])

  const run = useCallback(
    async (input: AnalysisInput) => {
      setBusy(true)
      setError("")
      try {
        const extras = optionsToPayload(options)
        let traceDoc: TraceDoc | null = null
        let result: Report
        let label: string
        if (input.kind === "scenario") {
          // Fetch the bundled trace so the explorer can show payloads.
          const t = (await api.example(input.id)) as unknown as TraceDoc
          traceDoc = Array.isArray(t?.events) ? t : null
          result = await api.analyze({ ...extras, scenario_id: input.id })
          label = `scenario ${input.id}`
        } else {
          const t = input.trace as TraceDoc
          traceDoc = Array.isArray(t?.events) ? t : null
          result = await api.analyze({ ...extras, trace: input.trace })
          label = input.label
        }
        setReport(result)
        setTrace(traceDoc)
        setResultLabel(label)
        setLastInput(input)
        setEditing(false)
        // Keep the masked report across a reload. Never the trace, and never a
        // report that carries raw values.
        try {
          if (options.redact)
            sessionStorage.setItem(SESSION_KEY, JSON.stringify({ report: result, label, scenarioId: input.kind === "scenario" ? input.id : undefined }))
          else sessionStorage.removeItem(SESSION_KEY)
        } catch {
          /* storage unavailable: the result simply does not survive a reload */
        }
        setParams(
          (p) => {
            const n = new URLSearchParams()
            if (input.kind === "scenario") n.set("scenario", input.id)
            const tab = p.get("tab")
            if (tab) n.set("tab", tab)
            return n
          },
          { replace: true },
        )
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setBusy(false)
      }
    },
    [options, setParams],
  )

  // ?scenario=… is a permalink to "analyze this bundled scenario with defaults".
  const autoRan = useRef(false)
  useEffect(() => {
    if (autoRan.current || !urlScenario || !scenarios.length) return
    autoRan.current = true
    if (saved?.scenarioId === urlScenario && report) {
      // Same result as before the reload; refetch the trace for the explorer.
      api.example(urlScenario).then((t) => setTrace(t as unknown as TraceDoc)).catch(() => {})
      return
    }
    if (scenarios.some((s) => s.id === urlScenario)) void run({ kind: "scenario", id: urlScenario })
  }, [urlScenario, scenarios, run, saved, report])

  function currentInput(): AnalysisInput | null {
    if (mode === "scenario") return scenarioId ? { kind: "scenario", id: scenarioId } : null
    if (mode === "file") return file ? { kind: "trace", trace: file.trace, label: file.name } : null
    if (!pasted.trim()) return null
    try {
      return { kind: "trace", trace: JSON.parse(pasted), label: "pasted trace" }
    } catch (e) {
      setError(`The pasted text is not valid JSON: ${(e as Error).message}`)
      return null
    }
  }

  function submit() {
    const input = currentInput()
    if (input) void run(input)
  }

  async function takeFile(f?: File) {
    if (!f) return
    setError("")
    try {
      const parsed = JSON.parse(await f.text())
      const events = Array.isArray(parsed?.events) ? parsed.events.length : null
      setFile({ name: f.name, trace: parsed, events })
      setMode("file")
    } catch {
      setError(`${f.name} is not valid JSON.`)
    } finally {
      if (fileRef.current) fileRef.current.value = ""
    }
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    void takeFile(e.dataTransfer.files?.[0])
  }

  const selected = scenarios.find((s) => s.id === scenarioId)
  const builtins = scenarios.filter((s) => s.source === "builtin")
  const others = scenarios.filter((s) => s.source !== "builtin")
  const ready = mode === "scenario" ? Boolean(scenarioId) : mode === "file" ? Boolean(file) : Boolean(pasted.trim())

  return (
    <div className="min-w-0">
      <PageHeader
        title="Analyze a trace"
        description="Score one captured agent trace. Nothing is executed and nothing leaves this machine; the result is kept only if you save it as a run."
      />

      {/* input */}
      {editing || !report ? (
        <section
          aria-label="Trace input"
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn("rounded-lg border border-border bg-card", dragging && "border-foreground/60 border-dashed")}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && ready && !busy) submit()
          }}
        >
          <div className="flex flex-wrap gap-1 border-b border-border px-3 pt-2" role="tablist" aria-label="Input type">
            {(
              [
                ["scenario", "Bundled scenario"],
                ["file", "Trace file"],
                ["paste", "Paste JSON"],
              ] as [Mode, string][]
            ).map(([m, label]) => (
              <button
                key={m}
                type="button"
                role="tab"
                aria-selected={mode === m}
                onClick={() => setMode(m)}
                className={cn(
                  "-mb-px border-b-2 px-3 py-2 text-[13px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  mode === m ? "border-foreground font-medium text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="p-4">
            {mode === "scenario" && (
              <div className="grid gap-4 md:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
                <label className="block text-[12px] text-muted-foreground">
                  Scenario
                  <select
                    value={scenarioId}
                    onChange={(e) => setScenarioId(e.target.value)}
                    className="mt-1 h-9 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground"
                  >
                    <optgroup label="Built-in (leak and clean pairs)">
                      {builtins.map((s) => (
                        <option key={s.id} value={s.id}>
                          {scenarioLabel(s)} · {s.domain} · expected {s.expected_outcome ?? "?"}
                        </option>
                      ))}
                    </optgroup>
                    {others.length > 0 && (
                      <optgroup label="Imported and custom">
                        {others.map((s) => (
                          <option key={s.id} value={s.id}>
                            {scenarioLabel(s)} · {s.domain}
                          </option>
                        ))}
                      </optgroup>
                    )}
                  </select>
                </label>
                {selected && (
                  <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-1 text-[13px]">
                    <dt className="text-muted-foreground">Id</dt>
                    <dd className="break-all font-mono text-[12px]">{selected.id}</dd>
                    <dt className="text-muted-foreground">Task</dt>
                    <dd>{selected.description || "–"}</dd>
                    <dt className="text-muted-foreground">Sensitive data</dt>
                    <dd className="break-words font-mono text-[12px]">{selected.sensitive_data.join(", ") || "–"}</dd>
                    {selected.expected_outcome && (
                      <>
                        <dt className="text-muted-foreground">Expected</dt>
                        <dd>{selected.expected_outcome === "leak" ? "leaks on internal channels" : "clean control"}</dd>
                      </>
                    )}
                  </dl>
                )}
              </div>
            )}

            {mode === "file" && (
              <div className="flex flex-col items-start gap-3 rounded-md border border-dashed border-border p-6 sm:flex-row sm:items-center">
                <input ref={fileRef} type="file" accept="application/json,.json" className="sr-only" id="trace-file" onChange={(e) => takeFile(e.target.files?.[0])} />
                <Button variant="outline" onClick={() => fileRef.current?.click()}>
                  <FileUp /> Choose a JSON file
                </Button>
                <p className="min-w-0 text-[13px] text-muted-foreground">
                  {file ? (
                    <>
                      <span className="break-all font-mono text-foreground">{file.name}</span>
                      {file.events !== null ? ` · ${file.events} events` : " · no events array: the server will try to convert it"}
                    </>
                  ) : (
                    "or drop it anywhere on this panel. AgentLeak traces, scenario specs and ai4privacy records are accepted."
                  )}
                </p>
              </div>
            )}

            {mode === "paste" && (
              <Textarea
                value={pasted}
                onChange={(e) => setPasted(e.target.value)}
                spellCheck={false}
                aria-label="Trace JSON"
                className="h-56 resize-y font-mono text-[12px]"
                placeholder={'{\n  "run_id": "support-001",\n  "agent_name": "support-bot",\n  "events": [\n    {"event_id": "e1", "channel": "user_input", "source": "user", "target": "agent", "content": "..."}\n  ]\n}'}
              />
            )}
          </div>

          <div className="border-t border-border px-4 py-3">
            <button
              type="button"
              aria-expanded={showOptions}
              onClick={() => setShowOptions((o) => !o)}
              className="inline-flex max-w-full items-start gap-1 rounded-sm text-left text-[12px] text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <ChevronRight className={cn("mt-px size-3.5 shrink-0 transition-transform motion-reduce:transition-none", showOptions && "rotate-90")} />
              <span>
                Options: <span className="text-foreground">{optionsSummary(options)}</span>
              </span>
            </button>
            {showOptions && (
              <div className="mt-4">
                <AnalysisOptions value={options} onChange={setOptions} />
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3 border-t border-border px-4 py-3">
            <Button onClick={submit} disabled={!ready || busy}>
              {busy ? <Loader2 className="animate-spin motion-reduce:animate-none" /> : <Play />}
              {busy ? "Analyzing" : "Analyze"}
            </Button>
            <span className="text-[12px] text-muted-foreground">
              <kbd className="rounded border border-border px-1 font-mono">Ctrl</kbd>+<kbd className="rounded border border-border px-1 font-mono">Enter</kbd> also runs it
            </span>
            {report && (
              <Button variant="ghost" size="sm" className="ml-auto" onClick={() => setEditing(false)}>
                Back to the last result
              </Button>
            )}
          </div>
          {error && (
            <p role="alert" className="border-t border-border px-4 py-3 text-[13px] text-sev-l4">
              {error}
            </p>
          )}
        </section>
      ) : (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-border bg-card px-4 py-2.5 text-[13px]">
          <span className="text-muted-foreground">Analysed</span>
          <span className="min-w-0 break-all font-mono">{resultLabel}</span>
          <span className="text-muted-foreground">·</span>
          <span className="min-w-0 text-muted-foreground">{optionsSummary(options)}</span>
          <span className="rounded border border-border px-1.5 py-0.5 text-[11px] text-muted-foreground">not saved</span>
          <Button variant="outline" size="sm" className="ml-auto" onClick={() => setEditing(true)}>
            Change input
          </Button>
        </div>
      )}

      <div className="mt-6">
        {busy && <ResultSkeleton />}
        {!busy && report && (
          <ResultsView
            report={report}
            trace={trace}
            onTrace={setTrace}
            actions={
              <Button size="sm" onClick={() => setSaveOpen(true)} disabled={!lastInput && !trace}>
                <Save /> Save as run
              </Button>
            }
          />
        )}
        {!busy && !report && (
          <p className="text-sm text-muted-foreground">
            The result appears here: a verdict per channel first, then findings, the trace and the score derivation.
          </p>
        )}
      </div>

      <SaveDialog
        open={saveOpen}
        onOpenChange={setSaveOpen}
        input={lastInput ?? (trace ? { kind: "trace", trace, label: resultLabel } : null)}
        options={options}
        onSaved={(id) => nav(`/runs/${id}`)}
      />
    </div>
  )
}

function SaveDialog({
  open,
  onOpenChange,
  input,
  options,
  onSaved,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  input: AnalysisInput | null
  options: OptionsState
  onSaved: (runId: string) => void
}) {
  const [projects, setProjects] = useState<Project[]>([])
  const [projectId, setProjectId] = useState("")
  const [newName, setNewName] = useState("")
  const [label, setLabel] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    api
      .projects()
      .then((ps) => {
        setProjects(ps)
        setProjectId((cur) => cur || ps[0]?.id || "new")
        if (!ps.length) setNewName("Ad-hoc analyses")
      })
      .catch((e) => toast.error((e as Error).message))
  }, [open])

  async function save() {
    if (!input) return
    setBusy(true)
    try {
      let pid = projectId
      if (pid === "new") {
        if (!newName.trim()) {
          toast.error("Name the new project")
          return
        }
        pid = (await api.createProject({ name: newName.trim(), agent_type: "generic" })).id
      }
      const extras = optionsToPayload(options)
      const body = {
        detectors: extras.detectors,
        redact: extras.redact,
        vault: extras.vault,
        custom_detectors: extras.custom_detectors,
        source: "analyze",
        label: label.trim(),
        ...(input.kind === "scenario" ? { scenario_id: input.id } : { trace: input.trace }),
      }
      const runResult = await api.createRun(pid, body)
      toast.success(`Saved as ${runResult.id}`)
      onOpenChange(false)
      onSaved(runResult.id)
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Save as run</DialogTitle>
          <DialogDescription>
            The trace is re-scored inside the project and only the report is stored, with values masked unless you turned
            masking off. The project's own detector settings are merged with these options.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 text-sm">
          <label className="block text-[12px] text-muted-foreground">
            Project
            <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="mt-1 h-9 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground">
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
              <option value="new">New project…</option>
            </select>
          </label>
          {projectId === "new" && (
            <label className="block text-[12px] text-muted-foreground">
              New project name
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} className="mt-1" />
            </label>
          )}
          <label className="block text-[12px] text-muted-foreground">
            Label (optional)
            <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. before-mitigation" className="mt-1" />
          </label>
          {options.gate && <p className="text-[12px] text-muted-foreground">The evaluation gate is not stored with runs; the saved run uses the engine's blocking rule.</p>}
        </div>
        <div className="mt-2 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={save} disabled={busy || !input}>
            {busy && <Loader2 className="animate-spin motion-reduce:animate-none" />} Save run
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
