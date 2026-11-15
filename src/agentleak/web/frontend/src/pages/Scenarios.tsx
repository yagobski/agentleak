// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import {
  Check,
  Download,
  Eye,
  Loader2,
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
import { DataTable, type Column } from "@/components/DataTable"

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

  // Everything the engine ships, whether or not this account has imported it.
  const available = useMemo(
    () => scenarios.length + packs.reduce((n, p) => n + (p.count - p.imported_count), 0),
    [scenarios, packs],
  )

  const packById = Object.fromEntries(packs.map((p) => [p.id, p]))
  const columns: Column<Scenario>[] = [
    {
      id: "name",
      header: "Scenario",
      value: (s) => scenarioTitle(s),
      cell: (s) => (
        <div className="min-w-[12rem] max-w-[22rem]">
          <div className="truncate" title={scenarioTitle(s)}>{scenarioTitle(s)}</div>
          <div className="truncate font-mono text-[11px] text-muted-foreground" title={s.id}>{s.id}</div>
        </div>
      ),
    },
    { id: "domain", header: "Domain", value: (s) => s.domain, cell: (s) => <span className="text-[12px]">{s.domain}</span> },
    {
      id: "expected",
      header: "Expected",
      value: (s) => s.expected_outcome ?? "",
      hideBelow: "sm",
      cell: (s) => <span className="text-[12px] text-muted-foreground">{s.expected_outcome ?? "–"}</span>,
    },
    {
      id: "sensitive_data",
      header: "Sensitive data",
      value: (s) => s.sensitive_data.join("; "),
      hideBelow: "lg",
      sortable: false,
      cell: (s) => (
        <span className="line-clamp-2 max-w-[18rem] font-mono text-[11px] text-muted-foreground" title={s.sensitive_data.join(", ")}>
          {s.sensitive_data.join(", ") || "–"}
        </span>
      ),
    },
    {
      id: "provenance",
      header: "Provenance",
      value: (s) => provenance(s, packById).text,
      hideBelow: "md",
      cell: (s) => {
        const p = provenance(s, packById)
        return p.url ? (
          <a href={p.url} target="_blank" rel="noreferrer noopener" className="text-[12px] underline decoration-border underline-offset-2 hover:decoration-foreground">
            {p.text}
          </a>
        ) : (
          <span className="text-[12px]">{p.text}</span>
        )
      },
    },
    {
      id: "actions",
      header: "",
      value: () => "",
      sortable: false,
      exportable: false,
      cell: (s) => (
        <div className="flex items-center justify-end gap-1 whitespace-nowrap">
          <Button variant="outline" size="sm" className="h-7 text-[12px]" asChild>
            <Link to={`/analyze?scenario=${encodeURIComponent(s.id)}`}>
              <Play /> Analyze
            </Link>
          </Button>
          <Button variant="ghost" size="sm" className="h-7 text-[12px]" onClick={() => onView(s)}>
            <Eye /> Trace
          </Button>
          {s.source !== "builtin" && (
            <Button variant="ghost" size="icon" className="size-7 text-muted-foreground hover:text-sev-l4" onClick={() => onDelete(s)} aria-label={`Delete ${s.id}`}>
              <Trash2 className="size-3.5" />
            </Button>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="min-w-0">
      <PageHeader
        title="Scenarios"
        description={
          // The library opens on 10 built-ins while /api/meta advertises 266.
          // The other 256 are in packs, in a section below the grid — off
          // screen — so the first impression is a tenth of what the product
          // says it has. Saying the number here costs one line and closes the
          // gap between the advertised figure and the visible one.
          available > scenarios.length
            ? `Packaged traces and test specs. ${scenarios.length} in your library, ${available} available: import a pack to add the rest.`
            : "Packaged traces and test specs. Analyze one, upload your own, or import a pack."
        }
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

      {/* packs first: they are where most scenarios live */}
      <section aria-labelledby="packs" className="mb-6">
        <h2 id="packs" className="mb-2 text-sm font-medium">Scenario packs</h2>
        <div className="overflow-x-auto rounded-lg border border-border bg-card">
          <table className="w-full min-w-[40rem] text-sm">
            <caption className="sr-only">Importable scenario packs with source and license</caption>
            <thead>
              <tr className="border-b border-border text-left text-[11px] text-muted-foreground">
                <th scope="col" className="px-4 py-2 font-medium">Pack</th>
                <th scope="col" className="px-3 py-2 font-medium">Source and license</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Imported</th>
                <th scope="col" className="px-4 py-2 text-right font-medium"><span className="sr-only">Action</span></th>
              </tr>
            </thead>
            <tbody>
              {packs.map((p) => (
                <PackRow key={p.id} pack={p} onImport={() => onImport(p)} />
              ))}
              {!packs.length && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">No pack is bundled with this build.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="library">
        <h2 id="library" className="mb-2 text-sm font-medium">Library</h2>
        <div className="rounded-lg border border-border bg-card">
          <DataTable
            caption="Scenario library"
            columns={columns}
            rows={filtered}
            rowKey={(s) => s.id}
            exportName="scenarios"
            pageSize={50}
            empty="No scenario matches these filters."
            toolbar={
              <>
                <div className="relative min-w-[160px] flex-1 sm:max-w-[18rem]">
                  <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                  <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Name, data type, tag" aria-label="Search scenarios" data-shortcut="search" className="h-8 pl-8 text-[13px]" />
                </div>
                <label className="sr-only" htmlFor="sc-source">Origin</label>
                <select id="sc-source" value={source} onChange={(e) => setSource(e.target.value as SourceFilter)} className="h-8 rounded-md border border-input bg-background px-2 text-[13px]">
                  <option value="all">All origins</option>
                  {(["builtin", "custom", "imported"] as const).map((m) => (
                    <option key={m} value={m}>
                      {SOURCE_LABEL[m]} ({counts[m]})
                    </option>
                  ))}
                </select>
                <label className="sr-only" htmlFor="sc-domain">Domain</label>
                <select id="sc-domain" value={domain} onChange={(e) => setDomain(e.target.value)} className="h-8 rounded-md border border-input bg-background px-2 text-[13px]">
                  <option value="all">All domains</option>
                  {domains.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </>
            }
          />
        </div>
      </section>

      <UploadDialog open={uploadOpen} onOpenChange={setUploadOpen} onDone={refresh} />
      <BuilderDialog open={builderOpen} onOpenChange={setBuilderOpen} onDone={refresh} />
      <TraceDialog
        detail={detail}
        onClose={() => setDetail(null)}
        onRun={(id) => {
          setDetail(null)
          nav(`/analyze?scenario=${encodeURIComponent(id)}`)
        }}
      />
    </div>
  )
}

function scenarioTitle(scenario: Scenario) {
  const raw = scenario.name && scenario.name !== scenario.id
    ? scenario.name
    : scenario.id.replace(new RegExp(`^${scenario.domain}_`), "").replace(/_/g, " ")
  return raw.charAt(0).toUpperCase() + raw.slice(1)
}

function provenance(s: Scenario, packs: Record<string, ScenarioPack>): { text: string; url?: string } {
  if ((s.source ?? "builtin") === "builtin") return { text: "AgentLeak built-in · synthetic · MIT" }
  if (s.source === "imported" && s.pack_id) {
    const p = packs[s.pack_id]
    return p ? { text: `${p.name} · ${p.license ?? "license not stated"}`, url: p.source_url } : { text: `pack ${s.pack_id}` }
  }
  return { text: "Uploaded in this workspace" }
}

function PackRow({ pack, onImport }: { pack: ScenarioPack; onImport: () => Promise<void> | void }) {
  const [busy, setBusy] = useState(false)
  const remaining = pack.count - pack.imported_count
  const done = remaining <= 0
  return (
    <tr className="border-b border-border/70 align-top last:border-b-0">
      <td className="px-4 py-2.5">
        <div className="font-medium">{pack.name}</div>
        <div className="mt-0.5 max-w-xl text-[12px] text-muted-foreground">{pack.description}</div>
      </td>
      <td className="px-3 py-2.5 text-[12px]">
        {pack.source_url ? (
          <a href={pack.source_url} target="_blank" rel="noreferrer noopener" className="underline decoration-border underline-offset-2 hover:decoration-foreground">
            {pack.source}
          </a>
        ) : (
          pack.source
        )}
        <div className="text-muted-foreground">{pack.license ?? "license not stated"}</div>
        {pack.attribution && <div className="mt-0.5 max-w-xs text-[11px] text-muted-foreground">{pack.attribution}</div>}
      </td>
      <td className="whitespace-nowrap px-3 py-2.5 text-right font-mono text-[12px] tnum">
        {pack.imported_count} / {pack.count}
      </td>
      <td className="px-4 py-2.5 text-right">
        <Button
          variant={done ? "ghost" : "outline"}
          size="sm"
          className="h-7 text-[12px]"
          disabled={busy || done}
          onClick={async () => {
            setBusy(true)
            await onImport()
            setBusy(false)
          }}
        >
          {busy ? <Loader2 className="animate-spin motion-reduce:animate-none" /> : done ? <Check /> : <Download />}
          {done ? "Imported" : pack.imported_count > 0 ? `Import ${remaining} more` : `Import ${pack.count}`}
        </Button>
      </td>
    </tr>
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
            <Play /> Analyze sample trace
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
