// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useCallback, useEffect, useId, useMemo, useState } from "react"
import { Loader2, RefreshCw, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { api, type AgentCardData, type CodeFinding, type CodeScanDetail, type CodeScanSummary, type Project } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { DataTable, type Column } from "@/components/DataTable"
import { FieldRow, Section } from "@/components/Section"
import { LevelChip } from "./Chips"
import { formatStamp } from "./RunsTable"

const CARD_TEMPLATE: AgentCardData = {
  name: "my-agent",
  description: "What this agent does",
  capabilities: ["example_capability"],
  tags: ["example"],
  examples: ["do the thing"],
  input_mode: "text",
  output_mode: "text",
  agent_protocol_version: "a2a-v1",
  endpoints: { "/chat": "Main endpoint", "/health": "Health check" },
  source: { type: "github", repo: "owner/repo", branch: "main" },
}

/** Agent identity (A2A agent card) and static code scans. */
export function AgentCardView({ project, onChange }: { project: Project; onChange: () => void }) {
  return (
    <div className="space-y-4">
      {project.agent_card && <CardSummary card={project.agent_card} />}
      <CardEditor project={project} onChange={onChange} />
      <CodeScanPanel project={project} />
    </div>
  )
}

// ------------------------------------------------------------ summary
function CardSummary({ card }: { card: AgentCardData }) {
  const declared = card.privacy?.declared_data_types ?? []
  const endpoints = Object.entries(card.endpoints ?? {})
  return (
    <Section title={<span className="font-mono">{card.name}</span>} description={card.description}>
      <dl className="grid gap-x-6 gap-y-3 px-4 py-3 text-[13px] sm:grid-cols-[10rem_minmax(0,1fr)]">
        <dt className="text-muted-foreground">Protocol</dt>
        <dd className="font-mono text-[12px]">
          {card.agent_protocol_version ?? "a2a-v1"} · {card.input_mode ?? "text"} to {card.output_mode ?? "text"}
          {card.framework ? ` · ${card.framework}` : ""}
        </dd>
        {card.source?.repo && (
          <>
            <dt className="text-muted-foreground">Code source</dt>
            <dd>
              <a className="font-mono text-[12px] underline decoration-border underline-offset-2 hover:decoration-foreground" href={`https://github.com/${card.source.repo}`} target="_blank" rel="noreferrer">
                {card.source.repo}
                {card.source.branch ? `@${card.source.branch}` : ""}
              </a>
            </dd>
          </>
        )}
        <dt className="text-muted-foreground">Capabilities ({card.capabilities.length})</dt>
        <dd className="font-mono text-[12px]">{card.capabilities.join(", ") || "none declared"}</dd>
        {endpoints.length > 0 && (
          <>
            <dt className="text-muted-foreground">Endpoints ({endpoints.length})</dt>
            <dd>
              <ul className="space-y-0.5">
                {endpoints.map(([path, desc]) => (
                  <li key={path} className="break-words">
                    <code className="font-mono text-[12px]">{path}</code> <span className="text-muted-foreground">{desc}</span>
                  </li>
                ))}
              </ul>
            </dd>
          </>
        )}
        <dt className="text-muted-foreground">Declared data types</dt>
        <dd className="font-mono text-[12px]">{declared.length ? declared.join(", ") : "none declared"}</dd>
      </dl>
    </Section>
  )
}

// ------------------------------------------------------------- editor
function CardEditor({ project, onChange }: { project: Project; onChange: () => void }) {
  const uid = useId()
  const [text, setText] = useState("")
  const [url, setUrl] = useState("")
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(!project.agent_card)
  const [confirmRemove, setConfirmRemove] = useState(false)

  useEffect(() => {
    setText(project.agent_card ? JSON.stringify(project.agent_card, null, 2) : "")
  }, [project.agent_card])

  const jsonError = useMemo(() => {
    if (!text.trim()) return null
    try {
      const parsed = JSON.parse(text)
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return "The card must be a JSON object."
      if (!String(parsed.name ?? "").trim()) return "'name' is required."
      if (!Array.isArray(parsed.capabilities) || parsed.capabilities.length === 0) return "'capabilities' must list at least one capability."
      return null
    } catch (e) {
      return e instanceof Error ? e.message : "Invalid JSON."
    }
  }, [text])

  async function save() {
    setBusy(true)
    try {
      await api.saveAgentCard(project.id, JSON.parse(text) as AgentCardData)
      toast.success("Agent card saved")
      onChange()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save the card")
    } finally {
      setBusy(false)
    }
  }

  async function fetchFromUrl() {
    if (!url.trim()) return
    setBusy(true)
    try {
      const res = await api.fetchAgentCard(project.id, url.trim())
      setText(JSON.stringify(res.agent_card, null, 2))
      toast.success("Card read from the agent's well-known endpoint and saved")
      onChange()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not fetch the card")
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    try {
      await api.deleteAgentCard(project.id)
      setText("")
      toast.success("Agent card removed")
      onChange()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not remove the card")
    }
  }

  const card = project.agent_card
  return (
    <Section
      title="Agent card"
      description={
        <>
          The agent's identity, capabilities and optional code source, as an A2A <code className="font-mono">AgentCard.json</code>.
          An agent can also register its own card with <code className="font-mono">POST /api/agent/register</code> and the project API key.
        </>
      }
      actions={
        <Button variant="outline" size="sm" className="h-8" aria-expanded={open} aria-controls={`${uid}-editor`} onClick={() => setOpen((v) => !v)}>
          {open ? "Close editor" : card ? "Edit card" : "Add a card"}
        </Button>
      }
    >
      {open && (
        <div id={`${uid}-editor`}>
          <FieldRow label="Read from a running agent" htmlFor={`${uid}-url`} help="Fetches /.well-known/agent-card.json from that address and saves it.">
            <div className="flex flex-wrap gap-2">
              <Input id={`${uid}-url`} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://agent.example.test" className="h-8 min-w-0 flex-1 text-[13px]" />
              <Button variant="outline" size="sm" className="h-8" onClick={fetchFromUrl} disabled={busy || !url.trim()}>
                Fetch
              </Button>
            </div>
          </FieldRow>
          <FieldRow label="Card (JSON)" htmlFor={`${uid}-json`} help={!text ? <button type="button" className="underline underline-offset-2" onClick={() => setText(JSON.stringify(CARD_TEMPLATE, null, 2))}>Start from a template</button> : undefined}>
            <Textarea
              id={`${uid}-json`}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder='{"name": "my-agent", "capabilities": ["..."]}'
              className="min-h-56 font-mono text-[12px]"
              spellCheck={false}
              aria-invalid={!!jsonError}
              aria-describedby={`${uid}-json-status`}
            />
            <p id={`${uid}-json-status`} className={jsonError ? "mt-1 text-[12px] text-sev-l4" : "mt-1 text-[12px] text-muted-foreground"} aria-live="polite">
              {jsonError ? `Not saved yet: ${jsonError}` : text.trim() ? "The card is valid JSON with a name and capabilities." : "Empty."}
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button size="sm" onClick={save} disabled={busy || !text.trim() || !!jsonError}>
                {busy && <Loader2 className="animate-spin motion-reduce:animate-none" />} Save card
              </Button>
              {card && (
                <Button variant="ghost" size="sm" className="text-sev-l4 hover:text-sev-l4" onClick={() => setConfirmRemove(true)} disabled={busy}>
                  <Trash2 /> Remove card
                </Button>
              )}
            </div>
          </FieldRow>
        </div>
      )}
      {!open && !card && <p className="px-4 py-3 text-[13px] text-muted-foreground">No agent card.</p>}
      <ConfirmDialog
        open={confirmRemove}
        onOpenChange={setConfirmRemove}
        title="Remove the agent card?"
        description="The card is removed from this project. Runs and code scans are kept."
        confirmLabel="Remove card"
        onConfirm={remove}
      />
    </Section>
  )
}

// --------------------------------------------------------- code scans
function CodeScanPanel({ project }: { project: Project }) {
  const uid = useId()
  const [scans, setScans] = useState<CodeScanSummary[] | null>(null)
  const [detail, setDetail] = useState<CodeScanDetail | null>(null)
  const [repo, setRepo] = useState(project.agent_card?.source?.repo ?? "")
  const [branch, setBranch] = useState(project.agent_card?.source?.branch ?? "main")
  const [busy, setBusy] = useState(false)
  const [active, setActive] = useState<string | null>(null)

  const reload = useCallback(() => {
    api.codeScans(project.id).then(setScans).catch(() => setScans([]))
  }, [project.id])
  useEffect(reload, [reload])

  async function runScan(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    try {
      const payload = repo.trim() ? { source: "github", repo: repo.trim(), branch: branch.trim() || "main" } : {}
      const scan = await api.runCodeScan(project.id, payload)
      setDetail(scan)
      setActive(null)
      reload()
      toast.success(`Scan stored: ${scan.result.findings.length} finding(s), score ${scan.score} / 100`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Scan failed")
    } finally {
      setBusy(false)
    }
  }

  async function openScan(sid: string) {
    try {
      setDetail(await api.codeScan(sid))
      setActive(null)
    } catch {
      toast.error("Could not load the scan")
    }
  }

  const scanColumns: Column<CodeScanSummary>[] = [
    {
      id: "source",
      header: "Source",
      value: (s) => s.source_ref || s.source_type,
      cell: (s) => (
        <button type="button" onClick={(e) => { e.stopPropagation(); openScan(s.id) }} aria-current={detail?.id === s.id || undefined} className="rounded-sm text-left underline decoration-border underline-offset-2 hover:decoration-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <span className="font-mono text-[12px]">{s.source_ref || "inline files"}</span>
        </button>
      ),
    },
    { id: "type", header: "Type", value: (s) => s.source_type, hideBelow: "sm", cell: (s) => <span className="font-mono text-[11px] text-muted-foreground">{s.source_type}</span> },
    { id: "findings", header: "Findings", value: (s) => s.findings_count, align: "right", cell: (s) => <span className="font-mono text-[12px]">{s.findings_count}</span> },
    { id: "score", header: "Score", value: (s) => s.score, align: "right", cell: (s) => <span className="font-mono text-[12px]">{s.score} / 100</span> },
    { id: "when", header: "Scanned", value: (s) => s.created_at, hideBelow: "md", cell: (s) => <span className="whitespace-nowrap font-mono text-[11px] text-muted-foreground">{formatStamp(s.created_at)}</span> },
  ]

  const findings = detail?.result.findings ?? []
  const rows = findings.map((f, i) => ({ ...f, _key: String(i) }))
  const tiers = detail?.result.detection?.tiers ?? []
  const byTier = detail?.result.summary.by_tier ?? {}
  const findingColumns: Column<CodeFinding & { _key: string }>[] = [
    { id: "level", header: "Level", value: (f) => f.level, cell: (f) => <LevelChip level={f.level} /> },
    {
      id: "where",
      header: "File",
      value: (f) => `${f.file}:${f.line}`,
      cell: (f) => (
        <button
          type="button"
          aria-expanded={active === f._key}
          onClick={(e) => {
            e.stopPropagation()
            setActive(active === f._key ? null : f._key)
          }}
          className="rounded-sm text-left font-mono text-[12px] underline decoration-border underline-offset-2 hover:decoration-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {f.file}:{f.line}
        </button>
      ),
    },
    { id: "rule", header: "Rule", value: (f) => f.rule, cell: (f) => <span className="text-[12px]">{f.rule}</span> },
    { id: "tier", header: "Tier", value: (f) => f.tier ?? "regex", hideBelow: "sm", cell: (f) => <span className="text-[12px] text-muted-foreground">{f.tier ?? "regex"}</span> },
    { id: "snippet", header: "Snippet (masked)", value: (f) => f.snippet, hideBelow: "md", sortable: false, cell: (f) => <code className="block max-w-[28rem] truncate font-mono text-[12px] text-muted-foreground">{f.snippet}</code> },
  ]

  return (
    <Section
      title="Static code scan"
      description="Scans the agent's source with the project's detectors plus code rules: hard-coded secrets, personal data in code, sensitive variables written to logs, high-entropy literals."
    >
      <form onSubmit={runScan} className="flex flex-wrap items-end gap-2 border-b border-border px-4 py-3">
        <div className="min-w-[12rem] flex-1">
          <label htmlFor={`${uid}-repo`} className="text-[12px] text-muted-foreground">
            GitHub repository (owner/name)
          </label>
          <Input id={`${uid}-repo`} value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="owner/repository" className="mt-1 h-8 text-[13px]" />
        </div>
        <div className="w-32">
          <label htmlFor={`${uid}-branch`} className="text-[12px] text-muted-foreground">
            Branch
          </label>
          <Input id={`${uid}-branch`} value={branch} onChange={(e) => setBranch(e.target.value)} className="mt-1 h-8 text-[13px]" />
        </div>
        <Button type="submit" size="sm" className="h-8" disabled={busy || (!repo.trim() && !project.agent_card?.source?.repo)}>
          {busy && <Loader2 className="animate-spin motion-reduce:animate-none" />} Scan code
        </Button>
      </form>

      {scans === null ? (
        <p className="px-4 py-3 text-[13px] text-muted-foreground">Loading…</p>
      ) : scans.length === 0 ? (
        <p className="px-4 py-3 text-[13px] text-muted-foreground">
          No code scan yet. Name a repository above, or declare a <code className="font-mono">source</code> in the agent card. An agent can scan its
          own code with <code className="font-mono">POST /api/agent/code</code>.
        </p>
      ) : (
        <DataTable
          caption="Code scans"
          columns={scanColumns}
          rows={scans}
          rowKey={(s) => s.id}
          initialSort={{ id: "when", dir: "desc" }}
          onRowClick={(s) => openScan(s.id)}
          activeKey={detail?.id ?? null}
          toolbar={
            <Button variant="ghost" size="sm" className="h-8" onClick={reload}>
              <RefreshCw /> Refresh
            </Button>
          }
        />
      )}

      {detail && (
        <div className="border-t border-border">
          <p className="px-4 pt-3 text-[13px]">
            <span className="font-mono">{detail.source_ref || detail.id}</span>: {findings.length} finding{findings.length === 1 ? "" : "s"} in{" "}
            {detail.result.summary.files_scanned} file{detail.result.summary.files_scanned === 1 ? "" : "s"}, score {detail.score} / 100 ({detail.verdict}).{" "}
            <span className="text-muted-foreground">
              Tiers that ran: {tiers.length ? tiers.map((t) => `${t}${byTier[t] != null ? ` (${byTier[t]})` : ""}`).join(", ") : "not recorded"}.
            </span>
          </p>
          {findings.length === 0 ? (
            <p className="px-4 py-3 text-[13px] text-muted-foreground">
              No finding from the enabled detectors in this scan. That is not proof the code handles personal data safely: code the rules do not
              recognise is not reported.
            </p>
          ) : (
            <DataTable
              caption="Code scan findings"
              columns={findingColumns}
              rows={rows}
              rowKey={(f) => f._key}
              initialSort={{ id: "level", dir: "desc" }}
              exportName={`code-scan-${detail.id}`}
              pageSize={50}
              onRowClick={(f) => setActive(active === f._key ? null : f._key)}
              activeKey={active}
              expanded={(f) =>
                active === f._key ? (
                  <div className="space-y-1 text-[13px]">
                    <p>
                      <span className="text-muted-foreground">Data type </span>
                      <code className="font-mono">{f.data_type}</code>
                      <span className="ml-3 text-muted-foreground">confidence </span>
                      <span className="tnum">{Math.round((f.confidence ?? 1) * 100)} %</span>
                    </p>
                    <code className="block break-all font-mono text-[12px] text-muted-foreground">{f.snippet}</code>
                    {f.recommendation && (
                      <p>
                        <span className="text-muted-foreground">Recommendation. </span>
                        {f.recommendation}
                      </p>
                    )}
                  </div>
                ) : null
              }
            />
          )}
        </div>
      )}
    </Section>
  )
}
