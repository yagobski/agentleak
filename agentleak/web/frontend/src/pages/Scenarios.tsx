import { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import {
  Check,
  Download,
  Eye,
  Loader2,
  Package,
  Play,
  Plus,
  Search,
  Trash2,
  Upload,
} from "lucide-react"
import { toast } from "sonner"
import { api, type Scenario, type ScenarioDetail, type ScenarioPack } from "@/lib/api"
import { download } from "@/lib/format"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { PageHeader } from "@/layout/AppShell"

type SourceFilter = "all" | "builtin" | "custom" | "imported"

const SOURCE_LABEL: Record<string, string> = {
  builtin: "Built-in",
  custom: "Custom",
  imported: "Imported",
}

function sourceVariant(source?: string): "default" | "secondary" | "muted" {
  if (source === "custom") return "default"
  if (source === "imported") return "muted"
  return "secondary"
}

export function Scenarios() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [packs, setPacks] = useState<ScenarioPack[]>([])
  const [query, setQuery] = useState("")
  const [domain, setDomain] = useState("all")
  const [source, setSource] = useState<SourceFilter>("all")
  const [uploadOpen, setUploadOpen] = useState(false)
  const [builderOpen, setBuilderOpen] = useState(false)
  const [detail, setDetail] = useState<ScenarioDetail | null>(null)
  const nav = useNavigate()

  function refresh() {
    api.scenarios().then(setScenarios).catch((e) => toast.error(e.message))
    api.scenarioPacks().then(setPacks).catch(() => {})
  }
  useEffect(refresh, [])

  const domains = useMemo(
    () => Array.from(new Set(scenarios.map((s) => s.domain))).sort(),
    [scenarios],
  )

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return scenarios.filter((s) => {
      if (domain !== "all" && s.domain !== domain) return false
      if (source !== "all" && (s.source ?? "builtin") !== source) return false
      if (!q) return true
      const hay = `${s.name ?? ""} ${s.id} ${s.description} ${s.sensitive_data.join(" ")} ${(s.tags ?? []).join(" ")}`
      return hay.toLowerCase().includes(q)
    })
  }, [scenarios, query, domain, source])

  async function onImport(pack: ScenarioPack) {
    try {
      const r = await api.importPack(pack.id)
      toast.success(
        r.imported
          ? `Imported ${r.imported} scenario${r.imported === 1 ? "" : "s"} from ${pack.name}`
          : `${pack.name} is already fully imported`,
      )
      refresh()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  async function onDelete(s: Scenario) {
    if (!window.confirm(`Delete scenario "${s.name ?? s.id}"? This cannot be undone.`)) return
    try {
      await api.deleteScenario(s.id)
      toast.success(`Deleted ${s.name ?? s.id}`)
      refresh()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  async function onView(s: Scenario) {
    try {
      setDetail(await api.scenario(s.id))
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const counts = useMemo(() => {
    const c = { builtin: 0, custom: 0, imported: 0 }
    for (const s of scenarios) c[(s.source ?? "builtin") as keyof typeof c]++
    return c
  }, [scenarios])

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Scenarios"
        description="A library of privacy test cases. Run them, upload your own, or import curated packs."
        actions={
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setBuilderOpen(true)}>
              <Plus /> Build scenario
            </Button>
            <Button onClick={() => setUploadOpen(true)}>
              <Upload /> Upload
            </Button>
          </div>
        }
      />

      {/* filters */}
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by name, data type, tag…"
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap items-center gap-1.5 rounded-md bg-muted p-1">
          {(["all", "builtin", "custom", "imported"] as SourceFilter[]).map((m) => (
            <button
              key={m}
              onClick={() => setSource(m)}
              className={`rounded px-2.5 py-1 text-xs font-medium capitalize transition-colors ${
                source === m ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {m === "all" ? "All" : SOURCE_LABEL[m]}
              {m !== "all" && <span className="ml-1 tnum opacity-60">{counts[m as keyof typeof counts]}</span>}
            </button>
          ))}
        </div>
      </div>

      {/* domain chips */}
      {domains.length > 1 && (
        <div className="mb-5 flex flex-wrap gap-1.5">
          <DomainChip active={domain === "all"} onClick={() => setDomain("all")}>
            All domains
          </DomainChip>
          {domains.map((d) => (
            <DomainChip key={d} active={domain === d} onClick={() => setDomain(d)}>
              {d}
            </DomainChip>
          ))}
        </div>
      )}

      {/* library */}
      {filtered.length === 0 ? (
        <Card className="p-10 text-center text-sm text-muted-foreground">
          No scenarios match. Try clearing filters, uploading a trace, or importing a pack below.
        </Card>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((s) => (
            <ScenarioCard
              key={s.id}
              scenario={s}
              onView={() => onView(s)}
              onRun={() => nav(`/playground?scenario=${s.id}`)}
              onDelete={() => onDelete(s)}
            />
          ))}
        </div>
      )}

      {/* packs */}
      <div className="mt-10">
        <div className="mb-3 flex items-center gap-2">
          <Package className="size-4 text-primary" />
          <h2 className="text-sm font-semibold">Scenario packs</h2>
          <span className="text-xs text-muted-foreground">Curated, ready-to-run — imported into your library.</span>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          {packs.map((p) => (
            <PackCard key={p.id} pack={p} onImport={() => onImport(p)} />
          ))}
        </div>
      </div>

      <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} onDone={refresh} />
      <BuilderDialog open={builderOpen} onOpenChange={setBuilderOpen} onDone={refresh} />
      <TraceDialog
        detail={detail}
        onClose={() => setDetail(null)}
        onRun={(id) => {
          setDetail(null)
          nav(`/playground?scenario=${id}`)
        }}
      />
    </div>
  )
}

function DomainChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full border px-3 py-1 text-xs font-medium capitalize transition-colors ${
        active
          ? "border-primary/40 bg-primary/15 text-primary"
          : "border-border text-muted-foreground hover:border-foreground/30 hover:text-foreground"
      }`}
    >
      {children}
    </button>
  )
}

function ScenarioCard({
  scenario: s,
  onView,
  onRun,
  onDelete,
}: {
  scenario: Scenario
  onView: () => void
  onRun: () => void
  onDelete: () => void
}) {
  return (
    <Card className="flex flex-col p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{s.name ?? s.id}</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-1.5">
            <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
              {s.domain}
            </span>
            {s.difficulty && (
              <span className="text-[10px] uppercase tracking-wide text-muted-foreground">{s.difficulty}</span>
            )}
          </div>
        </div>
        <Badge variant={sourceVariant(s.source)} className="shrink-0 text-[10px]">
          {SOURCE_LABEL[s.source ?? "builtin"]}
        </Badge>
      </div>

      <p className="mt-2 line-clamp-2 flex-1 text-sm text-muted-foreground">{s.description || "No description."}</p>

      {s.sensitive_data.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {s.sensitive_data.slice(0, 4).map((d) => (
            <span key={d} className="rounded-full bg-secondary px-2 py-0.5 text-[11px] text-secondary-foreground">
              {d}
            </span>
          ))}
          {s.sensitive_data.length > 4 && (
            <span className="px-1 py-0.5 text-[11px] text-muted-foreground">+{s.sensitive_data.length - 4}</span>
          )}
        </div>
      )}

      <div className="mt-4 flex items-center gap-1.5 border-t border-border pt-3">
        <Button variant="outline" size="sm" className="flex-1" onClick={onRun}>
          <Play /> Run
        </Button>
        <Button variant="ghost" size="sm" onClick={onView}>
          <Eye /> View
        </Button>
        {s.source !== "builtin" && (
          <Button variant="ghost" size="icon" className="size-8 text-muted-foreground hover:text-sev-l4" onClick={onDelete}>
            <Trash2 className="size-4" />
          </Button>
        )}
      </div>
    </Card>
  )
}

function PackCard({ pack, onImport }: { pack: ScenarioPack; onImport: () => void }) {
  const [busy, setBusy] = useState(false)
  const remaining = pack.count - pack.imported_count
  const done = remaining <= 0

  async function go() {
    setBusy(true)
    await onImport()
    setBusy(false)
  }

  return (
    <Card className="flex flex-col p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-medium">{pack.name}</div>
          <div className="mt-0.5 text-[11px] text-muted-foreground">
            {pack.count} scenarios · {pack.source}
          </div>
        </div>
        {pack.imported_count > 0 && (
          <Badge variant="muted" className="shrink-0 text-[10px]">
            {pack.imported_count} imported
          </Badge>
        )}
      </div>
      <p className="mt-2 flex-1 text-sm text-muted-foreground">{pack.description}</p>
      <Button
        variant={done ? "outline" : "default"}
        size="sm"
        className="mt-4"
        onClick={go}
        disabled={busy || done}
      >
        {busy ? <Loader2 className="animate-spin" /> : done ? <Check /> : <Download />}
        {done ? "All imported" : pack.imported_count > 0 ? `Import ${remaining} new` : "Import pack"}
      </Button>
    </Card>
  )
}

function UploadDialog({
  open,
  onOpenChange,
  onDone,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  onDone: () => void
}) {
  const [text, setText] = useState("")
  const [name, setName] = useState("")
  const [domainV, setDomainV] = useState("")
  const [busy, setBusy] = useState(false)

  async function submit() {
    let parsed: unknown
    try {
      parsed = JSON.parse(text)
    } catch {
      toast.error("That isn't valid JSON.")
      return
    }
    setBusy(true)
    try {
      const created = await api.createScenario({
        data: parsed,
        ...(name.trim() && { name: name.trim() }),
        ...(domainV.trim() && { domain: domainV.trim() }),
      })
      toast.success(`Added “${created.name ?? created.id}”`)
      setText("")
      setName("")
      setDomainV("")
      onOpenChange(false)
      onDone()
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Upload a scenario</DialogTitle>
          <DialogDescription>
            Paste an AgentLeak trace, an AgentLeak scenario spec, an ai4privacy record, or any
            OpenAI-style chat log (<code className="font-mono text-[11px]">{'{"messages": [...]}'}</code>).
            The format is detected automatically and converted into a runnable trace.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="eyebrow">Name (optional)</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="My scenario" />
            </div>
            <div className="space-y-1.5">
              <Label className="eyebrow">Domain (optional)</Label>
              <Input value={domainV} onChange={(e) => setDomainV(e.target.value)} placeholder="custom" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label className="eyebrow">JSON</Label>
            <Textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              spellCheck={false}
              className="h-56 resize-y font-mono text-[12px] leading-relaxed"
              placeholder='{ "agent_name": "...", "events": [ ... ] }'
            />
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={busy || !text.trim()}>
            {busy ? <Loader2 className="animate-spin" /> : <Upload />}
            Add scenario
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// guided scenario builder -> AgentLeak spec (runnable, leaky trace synthesized)
const ADVERSARY = [
  { id: "A0", label: "A0 · benign (light leakage)" },
  { id: "A1", label: "A1 · moderate (downstream tool leak)" },
  { id: "A2", label: "A2 · aggressive (broad, multi-channel)" },
]

function BuilderDialog({
  open,
  onOpenChange,
  onDone,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  onDone: () => void
}) {
  const [name, setName] = useState("")
  const [domainV, setDomainV] = useState("custom")
  const [task, setTask] = useState("")
  const [directive, setDirective] = useState("")
  const [adversary, setAdversary] = useState("A1")
  const [fields, setFields] = useState<{ key: string; value: string }[]>([
    { key: "name", value: "" },
    { key: "ssn", value: "" },
  ])
  const [busy, setBusy] = useState(false)

  function reset() {
    setName("")
    setDomainV("custom")
    setTask("")
    setDirective("")
    setAdversary("A1")
    setFields([
      { key: "name", value: "" },
      { key: "ssn", value: "" },
    ])
  }

  async function submit() {
    if (!name.trim()) return toast.error("Give the scenario a name")
    if (!task.trim()) return toast.error("Describe the agent's task")
    const filled = fields.filter((f) => f.key.trim() && f.value.trim())
    if (!filled.length) return toast.error("Add at least one sensitive field with a value")

    const spec = {
      scenario_id: name.trim(),
      vertical: domainV.trim() || "custom",
      objective: {
        user_request: task.trim(),
        ...(directive.trim() && { privacy_directive: directive.trim() }),
      },
      private_vault: {
        records: [
          {
            record_type: "record",
            fields: Object.fromEntries(filled.map((f) => [f.key.trim(), f.value.trim()])),
          },
        ],
      },
      tags: [`adversary:${adversary}`],
    }

    setBusy(true)
    try {
      const created = await api.createScenario({
        data: spec,
        name: name.trim(),
        domain: domainV.trim() || "custom",
      })
      toast.success(`Built “${created.name ?? created.id}”`)
      reset()
      onOpenChange(false)
      onDone()
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Build a scenario</DialogTitle>
          <DialogDescription>
            Describe a task and the private data the agent is trusted with. AgentLeak synthesizes a runnable test that
            checks whether your agents leak that data across channels.
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="max-h-[60vh] pr-3">
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="eyebrow">Name</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Patient discharge summary" />
              </div>
              <div className="space-y-1.5">
                <Label className="eyebrow">Domain</Label>
                <Input value={domainV} onChange={(e) => setDomainV(e.target.value)} placeholder="healthcare" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="eyebrow">Agent task</Label>
              <Textarea
                value={task}
                onChange={(e) => setTask(e.target.value)}
                placeholder="Summarize the patient's visit for the referral letter."
                className="h-16 text-sm"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="eyebrow">Privacy directive (optional)</Label>
              <Input
                value={directive}
                onChange={(e) => setDirective(e.target.value)}
                placeholder="Do not disclose the SSN or diagnosis."
              />
            </div>
            <div className="space-y-1.5">
              <Label className="eyebrow">Adversary pressure</Label>
              <Select value={adversary} onValueChange={setAdversary}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ADVERSARY.map((a) => (
                    <SelectItem key={a.id} value={a.id}>
                      {a.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="eyebrow">Private data (the vault)</Label>
                <button
                  onClick={() => setFields((f) => [...f, { key: "", value: "" }])}
                  className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
                >
                  <Plus className="size-3" /> Add field
                </button>
              </div>
              {fields.map((f, i) => (
                <div key={i} className="flex gap-1.5">
                  <Input
                    value={f.key}
                    placeholder="field (e.g. ssn)"
                    className="h-8 flex-1 font-mono text-xs"
                    onChange={(e) => setFields((s) => s.map((x, j) => (j === i ? { ...x, key: e.target.value } : x)))}
                  />
                  <Input
                    value={f.value}
                    placeholder="value (e.g. 123-45-6789)"
                    className="h-8 flex-[2] text-xs"
                    onChange={(e) => setFields((s) => s.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)))}
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-8 shrink-0"
                    onClick={() => setFields((s) => s.filter((_, j) => j !== i))}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              ))}
              <p className="text-[11px] text-muted-foreground">
                Fields like ssn, email, diagnosis, account_number are recognized as sensitive and tracked through the
                agents.
              </p>
            </div>
          </div>
        </ScrollArea>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={busy || !name.trim() || !task.trim()}>
            {busy ? <Loader2 className="animate-spin" /> : <Plus />}
            Build scenario
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

function TraceDialog({
  detail,
  onClose,
  onRun,
}: {
  detail: ScenarioDetail | null
  onClose: () => void
  onRun: (id: string) => void
}) {
  if (!detail) return null
  const events = (detail.trace?.events as unknown[]) ?? []
  return (
    <Dialog open={!!detail} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{detail.name ?? detail.id}</DialogTitle>
          <DialogDescription>{detail.description || "No description."}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant={sourceVariant(detail.source)} className="text-[10px]">
            {SOURCE_LABEL[detail.source ?? "builtin"]}
          </Badge>
          <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
            {detail.domain}
          </span>
          <span className="text-[11px] text-muted-foreground">{events.length} events</span>
        </div>
        {detail.sensitive_data.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {detail.sensitive_data.map((d) => (
              <span key={d} className="rounded-full bg-secondary px-2 py-0.5 text-[11px] text-secondary-foreground">
                {d}
              </span>
            ))}
          </div>
        )}
        <ScrollArea className="max-h-[40vh] rounded-md border border-border bg-muted/40">
          <pre className="p-3 font-mono text-[11px] leading-relaxed text-foreground/90">
            {JSON.stringify(detail.trace, null, 2)}
          </pre>
        </ScrollArea>
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => download(`${detail.id}.json`, JSON.stringify(detail.trace, null, 2), "application/json")}
          >
            <Download /> Download
          </Button>
          <Button onClick={() => onRun(detail.id)}>
            <Play /> Run in playground
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
