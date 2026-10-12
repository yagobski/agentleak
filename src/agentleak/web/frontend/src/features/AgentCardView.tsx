// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useCallback, useEffect, useMemo, useState } from "react"
import {
  BadgeCheck,
  ChevronDown,
  ChevronRight,
  FileCode2,
  Github,
  Globe,
  Loader2,
  Pencil,
  RefreshCw,
  Save,
  ShieldCheck,
  Trash2,
} from "lucide-react"
import { toast } from "sonner"
import {
  api,
  type AgentCardData,
  type CodeFinding,
  type CodeScanDetail,
  type CodeScanSummary,
  type Project,
} from "@/lib/api"
import { scoreColor } from "@/lib/format"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"

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

/** Agent identity (A2A card) + static code scan panel — the agent-first tab. */
export function AgentCardView({ project, onChange }: { project: Project; onChange: () => void }) {
  return (
    <div className="space-y-4">
      {project.agent_card && <CardSummary card={project.agent_card} />}
      <CardEditor project={project} onChange={onChange} />
      <CodeScanPanel project={project} />
    </div>
  )
}

// ------------------------------------------------------- Pretty summary
function CardSummary({ card }: { card: AgentCardData }) {
  const declared = card.privacy?.declared_data_types ?? []
  const endpoints = Object.entries(card.endpoints ?? {})
  return (
    <Card className="border-primary/25 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <ShieldCheck className="size-4 shrink-0 text-primary" />
            <span className="font-mono text-sm font-semibold">{card.name}</span>
            <Badge variant="muted">{card.agent_protocol_version ?? "a2a-v1"}</Badge>
            {card.framework && <Badge variant="muted">{card.framework}</Badge>}
            <Badge variant="muted">
              {card.input_mode ?? "text"} → {card.output_mode ?? "text"}
            </Badge>
          </div>
          {card.description && (
            <p className="mt-1 text-xs text-muted-foreground">{card.description}</p>
          )}
        </div>
        {card.source?.repo && (
          <a
            className="flex items-center gap-1.5 rounded border border-border px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
            href={`https://github.com/${card.source.repo}`}
            target="_blank"
            rel="noreferrer"
          >
            <Github className="size-3.5" />
            {card.source.repo}
            {card.source.branch ? `@${card.source.branch}` : ""}
          </a>
        )}
      </div>

      <div className="mt-3 grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Capabilities ({card.capabilities.length})
          </div>
          <div className="flex flex-wrap gap-1">
            {card.capabilities.map((c) => (
              <span key={c} className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px]">{c}</span>
            ))}
          </div>
        </div>
        {endpoints.length > 0 && (
          <div>
            <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Endpoints ({endpoints.length})
            </div>
            <div className="space-y-0.5">
              {endpoints.slice(0, 4).map(([path, desc]) => (
                <div key={path} className="truncate">
                  <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px]">{path}</code>{" "}
                  <span className="text-muted-foreground">{desc}</span>
                </div>
              ))}
              {endpoints.length > 4 && (
                <div className="text-muted-foreground">… and {endpoints.length - 4} more</div>
              )}
            </div>
          </div>
        )}
        {declared.length > 0 && (
          <div>
            <div className="mb-1 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Declared data types
            </div>
            <div className="flex flex-wrap gap-1">
              {declared.map((d) => (
                <span key={d} className="rounded bg-sev-l2/10 px-1.5 py-0.5 font-mono text-[11px] text-sev-l2">
                  {d}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}

// ------------------------------------------------------------ Card editor
function CardEditor({ project, onChange }: { project: Project; onChange: () => void }) {
  const [text, setText] = useState("")
  const [url, setUrl] = useState("")
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(!project.agent_card)

  useEffect(() => {
    setText(project.agent_card ? JSON.stringify(project.agent_card, null, 2) : "")
  }, [project.agent_card])

  // Live validation feedback while typing.
  const jsonError = useMemo(() => {
    if (!text.trim()) return null
    try {
      const parsed = JSON.parse(text)
      if (!parsed || typeof parsed !== "object") return "The card must be a JSON object."
      if (!String(parsed.name ?? "").trim()) return "'name' is required."
      if (!Array.isArray(parsed.capabilities) || parsed.capabilities.length === 0)
        return "'capabilities' should list at least one capability."
      return null
    } catch (e) {
      return e instanceof Error ? e.message : "Invalid JSON."
    }
  }, [text])

  async function save() {
    setBusy(true)
    try {
      await api.saveAgentCard(project.id, JSON.parse(text) as AgentCardData)
      toast.success("Agent card saved.")
      onChange()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not save the card.")
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
      toast.success("Card fetched from the agent's well-known endpoint.")
      onChange()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Could not fetch the card.")
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    setBusy(true)
    try {
      await api.deleteAgentCard(project.id)
      setText("")
      toast.success("Agent card removed.")
      onChange()
    } finally {
      setBusy(false)
    }
  }

  const card = project.agent_card

  return (
    <Card className="p-4">
      <button
        className="flex w-full items-center justify-between text-left"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="flex items-center gap-2">
          <BadgeCheck className="size-4 text-primary" />
          <h3 className="text-sm font-semibold">{card ? "Edit agent card" : "Agent card"}</h3>
          <span className="rounded bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
            A2A / Nasiko compatible
          </span>
        </div>
        {open ? <ChevronDown className="size-4 text-muted-foreground" /> : <Pencil className="size-3.5 text-muted-foreground" />}
      </button>

      {open && (
        <div className="mt-3">
          <p className="mb-3 text-xs text-muted-foreground">
            The card declares this agent's identity, capabilities, and (optionally) its code source —
            the same <code className="rounded bg-muted px-1 py-0.5">AgentCard.json</code> an A2A control
            plane like Nasiko uses. Agents can also self-register via{" "}
            <code className="rounded bg-muted px-1 py-0.5">POST /api/agent/register</code> with their API key.
          </p>

          <div className="mb-3 flex flex-wrap items-end gap-2">
            <div className="min-w-64 flex-1">
              <Label className="text-xs">Fetch from a live agent (well-known endpoint)</Label>
              <Input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://my-agent.example.com"
                className="mt-1"
              />
            </div>
            <Button variant="outline" size="sm" onClick={fetchFromUrl} disabled={busy || !url.trim()}>
              <Globe className="mr-1.5 size-3.5" /> Fetch
            </Button>
            {!text && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setText(JSON.stringify(CARD_TEMPLATE, null, 2))}
              >
                Use template
              </Button>
            )}
          </div>

          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder='{"name": "my-agent", "capabilities": ["..."]}'
            className={`min-h-56 font-mono text-xs ${jsonError ? "border-sev-l4/60" : text.trim() ? "border-sev-ok/40" : ""}`}
            spellCheck={false}
          />
          <div className="mt-1 h-4 text-[11px]">
            {jsonError ? (
              <span className="text-sev-l4">✗ {jsonError}</span>
            ) : text.trim() ? (
              <span className="text-sev-ok">✓ Valid agent card</span>
            ) : null}
          </div>
          <div className="mt-2 flex gap-2">
            <Button size="sm" onClick={save} disabled={busy || !text.trim() || !!jsonError}>
              {busy ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <Save className="mr-1.5 size-3.5" />}
              Save card
            </Button>
            {card && (
              <Button variant="ghost" size="sm" onClick={remove} disabled={busy}>
                <Trash2 className="mr-1.5 size-3.5" /> Remove
              </Button>
            )}
          </div>
        </div>
      )}
    </Card>
  )
}

// ------------------------------------------------------------- Code scans
function ScorePill({ score }: { score: number }) {
  return (
    <span className="tnum font-semibold" style={{ color: scoreColor(score) }}>
      {score}
      <span className="text-[10px] text-muted-foreground">/100</span>
    </span>
  )
}

function LevelPill({ level }: { level: number }) {
  const cls =
    level >= 4
      ? "bg-sev-l4/15 text-sev-l4"
      : level === 3
        ? "bg-sev-l3/15 text-sev-l3"
        : "bg-muted text-muted-foreground"
  return <span className={`rounded px-1.5 py-0.5 font-semibold ${cls}`}>L{level}</span>
}

function CodeScanPanel({ project }: { project: Project }) {
  const [scans, setScans] = useState<CodeScanSummary[]>([])
  const [detail, setDetail] = useState<CodeScanDetail | null>(null)
  const [repo, setRepo] = useState(project.agent_card?.source?.repo ?? "")
  const [branch, setBranch] = useState(project.agent_card?.source?.branch ?? "main")
  const [busy, setBusy] = useState(false)
  const [expanded, setExpanded] = useState<number | null>(null)

  const reload = useCallback(() => {
    api.codeScans(project.id).then(setScans).catch(() => {})
  }, [project.id])
  useEffect(reload, [reload])

  async function runScan() {
    setBusy(true)
    try {
      const payload = repo.trim()
        ? { source: "github", repo: repo.trim(), branch: branch.trim() || "main" }
        : {}
      const scan = await api.runCodeScan(project.id, payload)
      setDetail(scan)
      setExpanded(null)
      reload()
      toast.success(`Scan finished — score ${scan.score}/100 (${scan.verdict}).`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Scan failed.")
    } finally {
      setBusy(false)
    }
  }

  async function openScan(sid: string) {
    try {
      setDetail(await api.codeScan(sid))
      setExpanded(null)
    } catch {
      toast.error("Could not load the scan.")
    }
  }

  const byTier = detail?.result.summary.by_tier ?? {}

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center gap-2">
        <FileCode2 className="size-4 text-primary" />
        <h3 className="text-sm font-semibold">Static code scan</h3>
        <span className="rounded bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
          3-tier pipeline + entropy + de-obfuscation
        </span>
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        Runs the same hybrid detection stack as trace analysis (regex, Presidio, LLM-judge — per
        project settings) plus code-specific layers: hardcoded secrets, PII in code, sensitive
        variables in logs, decomposed PII, high-entropy literals, and quasi-identifier combinations.
      </p>

      <div className="mb-4 flex flex-wrap items-end gap-2">
        <div className="min-w-56 flex-1">
          <Label className="text-xs">GitHub repository (owner/name)</Label>
          <Input value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="acme/support-bot" className="mt-1" />
        </div>
        <div className="w-36">
          <Label className="text-xs">Branch</Label>
          <Input value={branch} onChange={(e) => setBranch(e.target.value)} className="mt-1" />
        </div>
        <Button size="sm" onClick={runScan} disabled={busy || (!repo.trim() && !project.agent_card?.source?.repo)}>
          {busy ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <Github className="mr-1.5 size-3.5" />}
          Scan code
        </Button>
      </div>

      {scans.length === 0 && !busy && (
        <div className="rounded-md border border-dashed border-border px-4 py-6 text-center text-xs text-muted-foreground">
          No code scans yet. Point at a GitHub repo (or declare a <code>source</code> in the agent
          card) and run the first scan — agents can also self-scan via{" "}
          <code className="rounded bg-muted px-1 py-0.5">POST /api/agent/code</code>.
        </div>
      )}

      {scans.length > 0 && (
        <>
          <Separator className="my-3" />
          <div className="mb-2 flex items-center justify-between">
            <h4 className="text-xs font-medium text-muted-foreground">Scan history ({scans.length})</h4>
            <Button variant="ghost" size="sm" onClick={reload}>
              <RefreshCw className="size-3.5" />
            </Button>
          </div>
          <div className="space-y-1.5">
            {scans.map((s) => (
              <button
                key={s.id}
                onClick={() => openScan(s.id)}
                className={`flex w-full items-center justify-between rounded border px-3 py-2 text-left text-xs hover:bg-muted/50 ${detail?.id === s.id ? "border-primary/50 bg-muted/30" : "border-border/60"}`}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] uppercase text-muted-foreground">
                    {s.source_type}
                  </span>
                  <span className="truncate">{s.source_ref || "inline files"}</span>
                </span>
                <span className="flex shrink-0 items-center gap-3">
                  <span className="text-muted-foreground">{s.findings_count} findings</span>
                  <ScorePill score={s.score} />
                  <span className="text-muted-foreground">{new Date(s.created_at * 1000).toLocaleString()}</span>
                </span>
              </button>
            ))}
          </div>
        </>
      )}

      {detail && (
        <>
          <Separator className="my-3" />
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-xs font-medium">
              {detail.source_ref || detail.id} — {detail.verdict} (<ScorePill score={detail.score} />
              ), {detail.result.summary.files_scanned} files scanned
            </h4>
            {detail.result.detection && (
              <div className="flex flex-wrap gap-1">
                {detail.result.detection.tiers.map((t) => (
                  <span key={t} className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                    {t}
                    {byTier[t] != null ? ` · ${byTier[t]}` : ""}
                  </span>
                ))}
              </div>
            )}
          </div>
          {detail.result.findings.length === 0 ? (
            <p className="text-xs text-muted-foreground">No static findings — clean scan.</p>
          ) : (
            <div className="max-h-96 overflow-auto rounded border border-border/60">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-muted/80 text-left text-muted-foreground">
                  <tr>
                    <th className="w-6 px-2 py-1.5" />
                    <th className="px-2 py-1.5 font-medium">Level</th>
                    <th className="px-2 py-1.5 font-medium">File</th>
                    <th className="px-2 py-1.5 font-medium">Rule</th>
                    <th className="px-2 py-1.5 font-medium">Tier</th>
                    <th className="px-2 py-1.5 font-medium">Snippet</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.result.findings.map((f, i) => (
                    <FindingRow
                      key={i}
                      finding={f}
                      expanded={expanded === i}
                      onToggle={() => setExpanded(expanded === i ? null : i)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </Card>
  )
}

function FindingRow({
  finding: f,
  expanded,
  onToggle,
}: {
  finding: CodeFinding
  expanded: boolean
  onToggle: () => void
}) {
  return (
    <>
      <tr
        className="cursor-pointer border-t border-border/40 align-top hover:bg-muted/30"
        onClick={onToggle}
      >
        <td className="px-2 py-1.5 text-muted-foreground">
          {expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        </td>
        <td className="px-2 py-1.5">
          <LevelPill level={f.level} />
        </td>
        <td className="px-2 py-1.5 font-mono">{f.file}:{f.line}</td>
        <td className="px-2 py-1.5">{f.rule}</td>
        <td className="px-2 py-1.5 text-muted-foreground">{f.tier ?? "regex"}</td>
        <td className="max-w-96 truncate px-2 py-1.5 font-mono text-muted-foreground">{f.snippet}</td>
      </tr>
      {expanded && (
        <tr className="border-t border-border/20 bg-muted/20">
          <td />
          <td colSpan={5} className="px-2 py-2">
            <div className="space-y-1 text-[11px]">
              <div>
                <span className="text-muted-foreground">data type </span>
                <code className="rounded bg-muted px-1 py-0.5 font-mono">{f.data_type}</code>
                <span className="ml-3 text-muted-foreground">confidence </span>
                <span className="tnum">{Math.round((f.confidence ?? 1) * 100)}%</span>
              </div>
              <div className="font-mono text-muted-foreground">{f.snippet}</div>
              {f.recommendation && <div className="text-foreground">→ {f.recommendation}</div>}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}
