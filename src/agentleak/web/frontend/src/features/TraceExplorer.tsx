// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useEffect, useMemo, useRef, useState } from "react"
import { ArrowRight, ChevronLeft, ChevronRight, Eye, EyeOff, FileUp, Search } from "lucide-react"
import { toast } from "sonner"
import { api, type Finding, type LeakPath, type LeakStep, type Report, type TraceDoc, type TraceEvent } from "@/lib/api"
import { channelSplit, useMeta } from "@/lib/meta"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { LevelChip } from "./Chips"

const PAGE = 100

interface Row {
  index: number
  event: TraceEvent
  findings: Finding[]
  /** Sensitive values that entered the agent at this event (vault sources). */
  entered: LeakPath[]
}

function naturalCompare(a: string, b: string) {
  return a.localeCompare(b, undefined, { numeric: true })
}

/** Without the trace, rebuild the events the report knows about: those carrying a finding or a leak-path step. */
export function reconstructEvents(report: Report): TraceEvent[] {
  const byId = new Map<string, TraceEvent>()
  const add = (s: { event_id?: string; channel: string; source: string; target: string }) => {
    if (s.event_id && !byId.has(s.event_id))
      byId.set(s.event_id, { event_id: s.event_id, channel: s.channel, source: s.source, target: s.target })
  }
  report.leak_paths?.forEach((p) => p.steps.forEach(add))
  report.findings.forEach(add)
  return [...byId.values()].sort((a, b) => naturalCompare(a.event_id, b.event_id))
}

/** Check that a trace is the one this report was computed from. */
export function traceMatchesReport(trace: TraceDoc, report: Report): string | null {
  if (!Array.isArray(trace?.events)) return "The file has no events array."
  if (trace.events.length !== report.event_count)
    return `The file has ${trace.events.length} events; this report was computed from ${report.event_count}.`
  const ids = new Set(trace.events.map((e) => e.event_id))
  const missing = report.findings.filter((f) => f.event_id && !ids.has(f.event_id))
  if (missing.length) return `${missing.length} finding(s) point to events that are not in this file.`
  return null
}

function dedupeSteps(steps: LeakStep[]): LeakStep[] {
  const seen = new Set<string>()
  return steps.filter((s) => {
    const k = `${s.event_id}|${s.kind}`
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })
}

/** Masked view: structure and sizes stay visible, values do not. */
export function maskContent(content: unknown, depth = 0): unknown {
  if (content === null || content === undefined) return content
  if (typeof content === "string") return `‹hidden · ${content.length} chars›`
  if (typeof content === "number" || typeof content === "boolean") return "‹hidden›"
  if (Array.isArray(content)) return depth > 4 ? `‹hidden · ${content.length} items›` : content.map((c) => maskContent(c, depth + 1))
  if (typeof content === "object") {
    if (depth > 4) return "‹hidden object›"
    return Object.fromEntries(Object.entries(content as Record<string, unknown>).map(([k, v]) => [k, maskContent(v, depth + 1)]))
  }
  return "‹hidden›"
}

function pretty(content: unknown): string {
  return typeof content === "string" ? content : JSON.stringify(content, null, 2)
}

function shortTime(ts?: string) {
  if (!ts) return ""
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ts
  return d.toISOString().slice(11, 23)
}

export function TraceExplorer({
  report,
  trace,
  onTrace,
  focusEvent,
  onFocusEvent,
  onShowFinding,
  initialChannel,
}: {
  report: Report
  trace: TraceDoc | null
  /** Called when the user loads the original trace into a stored run (kept in memory only). */
  onTrace?: (trace: TraceDoc) => void
  focusEvent: string | null
  onFocusEvent: (eventId: string | null) => void
  onShowFinding?: (findingId: string) => void
  /** Open with only this channel shown. */
  initialChannel?: string | null
}) {
  const meta = useMeta()
  const split = channelSplit(meta)
  const [hidden, setHidden] = useState<Set<string>>(() => {
    if (!initialChannel) return new Set()
    const evs = trace?.events?.length ? trace.events : reconstructEvents(report)
    return new Set(evs.map((e) => e.channel).filter((c) => c !== initialChannel))
  })
  const [onlyFindings, setOnlyFindings] = useState(false)
  const [q, setQ] = useState("")
  const [page, setPage] = useState(0)
  const [revealed, setRevealed] = useState<Set<string>>(new Set())
  const fileRef = useRef<HTMLInputElement>(null)

  const events = useMemo(() => (trace?.events?.length ? trace.events : reconstructEvents(report)), [trace, report])
  const full = Boolean(trace?.events?.length)

  const rows: Row[] = useMemo(() => {
    const fByEvent = new Map<string, Finding[]>()
    for (const f of report.findings) {
      if (!f.event_id) continue
      fByEvent.set(f.event_id, [...(fByEvent.get(f.event_id) ?? []), f])
    }
    const enteredByEvent = new Map<string, LeakPath[]>()
    for (const p of report.leak_paths ?? []) {
      for (const s of dedupeSteps(p.steps)) {
        if (s.kind !== "source") continue
        enteredByEvent.set(s.event_id, [...(enteredByEvent.get(s.event_id) ?? []), p])
      }
    }
    return events.map((event, index) => ({
      index,
      event,
      findings: (fByEvent.get(event.event_id) ?? []).sort((a, b) => b.level - a.level),
      entered: enteredByEvent.get(event.event_id) ?? [],
    }))
  }, [events, report])

  const channelCounts = useMemo(() => {
    const m: Record<string, number> = {}
    rows.forEach((r) => (m[r.event.channel] = (m[r.event.channel] ?? 0) + 1))
    return m
  }, [rows])
  const present = Object.keys(channelCounts)
  const sourceChans = present.filter((c) => split.isSource(c))
  const emissionChans = present.filter((c) => !split.isSource(c))

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return rows.filter((r) => {
      if (hidden.has(r.event.channel)) return false
      if (onlyFindings && !r.findings.length && !r.entered.length) return false
      if (needle) {
        const hay = `${r.event.event_id} ${r.event.channel} ${r.event.source ?? ""} ${r.event.target ?? ""} ${r.findings.map((f) => f.data_type).join(" ")}`.toLowerCase()
        if (!hay.includes(needle)) return false
      }
      return true
    })
  }, [rows, hidden, onlyFindings, q])

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE))

  // Jump to a focused event: make sure it is not filtered out, open its page,
  // scroll to it. Runs when the focus changes, not on every filter keystroke.
  const latest = useRef({ filtered, rows })
  latest.current = { filtered, rows }
  const [jumpTick, setJumpTick] = useState(0)
  useEffect(() => {
    if (!focusEvent) return
    const { filtered: f, rows: all } = latest.current
    const idx = f.findIndex((r) => r.event.event_id === focusEvent)
    if (idx < 0 && all.some((r) => r.event.event_id === focusEvent)) {
      setHidden(new Set())
      setOnlyFindings(false)
      setQ("")
      setJumpTick((t) => t + 1) // retry once the filters are cleared
      return
    }
    if (idx < 0) return
    setPage(Math.floor(idx / PAGE))
    const t = window.setTimeout(() => {
      document.getElementById(`evt-${focusEvent}`)?.scrollIntoView({ block: "nearest", behavior: "auto" })
    }, 30)
    return () => window.clearTimeout(t)
  }, [focusEvent, jumpTick])

  useEffect(() => {
    if (page >= pages) setPage(0)
  }, [page, pages])

  function toggleChannel(c: string) {
    setHidden((h) => {
      const n = new Set(h)
      if (n.has(c)) n.delete(c)
      else n.add(c)
      return n
    })
  }

  function adopt(doc: unknown, origin: string) {
    const t = doc as TraceDoc
    const problem = traceMatchesReport(t, report)
    if (problem) {
      toast.error(`${origin} does not match this run. ${problem}`)
      return
    }
    onTrace?.(t)
    toast.success(`Trace loaded from ${origin}. Kept in this tab only; nothing was uploaded.`)
  }

  async function loadFile(file?: File) {
    if (!file) return
    try {
      adopt(JSON.parse(await file.text()), file.name)
    } catch {
      toast.error("That file is not valid JSON.")
    } finally {
      if (fileRef.current) fileRef.current.value = ""
    }
  }

  async function loadScenario() {
    if (!report.scenario_id) return
    try {
      adopt(await api.example(report.scenario_id), `scenario ${report.scenario_id}`)
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  const visible = filtered.slice(page * PAGE, page * PAGE + PAGE)

  return (
    <div className="min-w-0">
      {!full && (
        <div className="border-b border-border bg-muted/30 px-4 py-3 text-[13px]">
          <p>
            Stored runs keep the report, not the trace. Showing <b className="tnum">{events.length}</b> of{" "}
            <b className="tnum">{report.event_count}</b> events, rebuilt from findings and leak paths, without payloads.
          </p>
          {onTrace && (
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <input ref={fileRef} type="file" accept="application/json,.json" className="sr-only" tabIndex={-1} onChange={(e) => loadFile(e.target.files?.[0])} aria-label="Original trace file" />
              <Button variant="outline" size="sm" className="h-8" onClick={() => fileRef.current?.click()}>
                <FileUp /> Load original trace file
              </Button>
              {report.scenario_id && (
                <Button variant="ghost" size="sm" className="h-8" onClick={loadScenario}>
                  Load bundled trace for <code className="font-mono">{report.scenario_id}</code>
                </Button>
              )}
              <span className="text-[12px] text-muted-foreground">Read in this browser tab and checked against the report; never uploaded.</span>
            </div>
          )}
        </div>
      )}

      {/* filters */}
      <div className="space-y-2 border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[180px] flex-1 sm:max-w-xs">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Event id, actor, data type"
              aria-label="Filter events"
              className="h-8 pl-8 text-[13px]"
            />
          </div>
          <label className="inline-flex items-center gap-1.5 text-[12px]">
            <input type="checkbox" className="size-3.5 accent-foreground" checked={onlyFindings} onChange={(e) => setOnlyFindings(e.target.checked)} />
            Only events with findings or vault entries
          </label>
          <span className="ml-auto text-[11px] tnum text-muted-foreground" aria-live="polite">
            {filtered.length} of {rows.length} events
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5" role="group" aria-label="Channels">
          {[
            ["Sources", sourceChans],
            ["Emissions", emissionChans],
          ].map(([label, chans]) =>
            (chans as string[]).length ? (
              <div key={label as string} className="flex flex-wrap items-center gap-1">
                <span className="mr-0.5 text-[11px] text-muted-foreground">{label as string}</span>
                {(chans as string[]).map((c) => {
                  const on = !hidden.has(c)
                  return (
                    <button
                      key={c}
                      type="button"
                      aria-pressed={on}
                      onClick={() => toggleChannel(c)}
                      className={cn(
                        "rounded border px-1.5 py-0.5 font-mono text-[11px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        on ? "border-foreground/30 text-foreground" : "border-border text-muted-foreground line-through",
                        split.isSource(c) && "border-dashed",
                      )}
                    >
                      {c} <span className="tnum opacity-70">{channelCounts[c]}</span>
                    </button>
                  )
                })}
              </div>
            ) : null,
          )}
        </div>
      </div>

      {/* timeline */}
      <ol className="divide-y divide-border/70" aria-label="Trace events">
        {visible.length === 0 && <li className="px-4 py-10 text-center text-sm text-muted-foreground">No event matches these filters.</li>}
        {visible.map((r) => {
          const e = r.event
          const isSource = split.isSource(e.channel)
          const open = focusEvent === e.event_id
          const isRevealed = revealed.has(e.event_id)
          return (
            <li key={e.event_id} id={`evt-${e.event_id}`} className={cn("scroll-mt-24", open && "bg-muted/50")}>
              <button
                type="button"
                aria-expanded={open}
                onClick={() => onFocusEvent(open ? null : e.event_id)}
                className="grid w-full grid-cols-[2.5rem_minmax(0,1fr)] items-start gap-x-3 px-4 py-2 text-left hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring sm:grid-cols-[2.5rem_5.5rem_minmax(9rem,12rem)_minmax(0,1fr)_auto]"
              >
                <span className="pt-0.5 font-mono text-[11px] tnum text-muted-foreground">{r.index + 1}</span>
                <span className={cn("hidden pt-0.5 text-[11px] sm:block", isSource ? "text-muted-foreground" : "text-foreground")}>
                  {isSource ? "source ↘" : "emission ↗"}
                </span>
                <span className="min-w-0">
                  <span className={cn("block truncate font-mono text-[13px]", isSource && "text-muted-foreground")}>{e.channel}</span>
                  <span className="block font-mono text-[11px] text-muted-foreground sm:hidden">{isSource ? "source" : "emission"}</span>
                </span>
                <span className="col-start-2 min-w-0 text-[12px] text-muted-foreground sm:col-start-auto">
                  <span className="inline-flex max-w-full items-center gap-1">
                    <span className="truncate">{e.source ?? "?"}</span>
                    <ArrowRight className="size-3 shrink-0" aria-label="to" />
                    <span className="truncate">{e.target ?? "?"}</span>
                  </span>
                  <span className="ml-2 font-mono text-[11px] opacity-80">{e.event_id}</span>
                </span>
                <span className="col-start-2 flex flex-wrap items-center gap-1 sm:col-start-auto sm:justify-end">
                  {r.findings.length > 0 && (
                    <>
                      <LevelChip level={r.findings[0].level} />
                      <span className="text-[12px]">
                        {r.findings.length} finding{r.findings.length === 1 ? "" : "s"}
                      </span>
                    </>
                  )}
                  {r.entered.length > 0 && (
                    <span className="text-[12px] text-muted-foreground">{r.entered.length} value{r.entered.length === 1 ? "" : "s"} entered</span>
                  )}
                  {e.timestamp && <span className="hidden font-mono text-[11px] text-muted-foreground lg:inline">{shortTime(e.timestamp)}</span>}
                </span>
              </button>

              {open && (
                <div className="space-y-3 px-4 pb-4 sm:pl-[3.25rem]">
                  {r.findings.length > 0 && (
                    <div>
                      <h4 className="mb-1.5 text-[11px] font-medium text-muted-foreground">Findings on this event</h4>
                      <ul className="space-y-2">
                        {r.findings.map((f) => (
                          <li key={f.finding_id} className="rounded-md border border-border p-2.5">
                            <div className="flex flex-wrap items-center gap-2 text-[13px]">
                              <LevelChip level={f.level} />
                              <span>{f.data_type}</span>
                              <code className="font-mono text-[12px]">{f.redacted_value}</code>
                              <span className="text-[11px] text-muted-foreground">{f.detector}</span>
                              {onShowFinding && (
                                <button type="button" className="ml-auto text-[11px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline" onClick={() => onShowFinding(f.finding_id)}>
                                  {f.finding_id} in findings table
                                </button>
                              )}
                            </div>
                            <LeakPathChain report={report} finding={f} current={e.event_id} onJump={onFocusEvent} />
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {r.entered.length > 0 && (
                    <div>
                      <h4 className="mb-1.5 text-[11px] font-medium text-muted-foreground">Values that entered the agent here and later leaked</h4>
                      <ul className="flex flex-wrap gap-1.5">
                        {r.entered.map((p, i) => (
                          <li key={i} className="inline-flex items-center gap-1.5 rounded border border-dashed border-border px-2 py-1 text-[12px]">
                            <LevelChip level={p.level} />
                            {p.data_type} <code className="font-mono">{p.value}</code>
                            <span className="text-muted-foreground">→ {p.channels.join(", ")}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <div>
                    <div className="mb-1.5 flex items-center gap-2">
                      <h4 className="text-[11px] font-medium text-muted-foreground">Payload</h4>
                      {full && e.content !== undefined && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-[12px]"
                          aria-pressed={isRevealed}
                          onClick={() =>
                            setRevealed((s) => {
                              const n = new Set(s)
                              if (n.has(e.event_id)) n.delete(e.event_id)
                              else n.add(e.event_id)
                              return n
                            })
                          }
                        >
                          {isRevealed ? <EyeOff /> : <Eye />} {isRevealed ? "Mask values" : "Reveal values"}
                        </Button>
                      )}
                    </div>
                    {full ? (
                      e.content === undefined ? (
                        <p className="text-[12px] text-muted-foreground">This event has no content.</p>
                      ) : (
                        <pre
                          className={cn(
                            "max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-md border border-border bg-muted/40 p-3 font-mono text-[12px] leading-relaxed",
                            isRevealed && "border-sev-l2/50",
                          )}
                        >
                          {pretty(isRevealed ? e.content : maskContent(e.content))}
                        </pre>
                      )
                    ) : (
                      <p className="text-[12px] text-muted-foreground">Not stored with this run. Load the original trace to inspect it.</p>
                    )}
                    {isRevealed && <p className="mt-1 text-[11px] text-sev-l2">Raw values shown. They stay in this tab and are masked again when you leave.</p>}
                  </div>
                </div>
              )}
            </li>
          )
        })}
      </ol>

      {pages > 1 && (
        <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
          <span className="tnum">
            {page * PAGE + 1}–{Math.min(filtered.length, (page + 1) * PAGE)} of {filtered.length}
          </span>
          <Button variant="ghost" size="icon" className="size-7" disabled={page === 0} onClick={() => setPage(page - 1)} aria-label="Previous page">
            <ChevronLeft />
          </Button>
          <Button variant="ghost" size="icon" className="size-7" disabled={page >= pages - 1} onClick={() => setPage(page + 1)} aria-label="Next page">
            <ChevronRight />
          </Button>
        </div>
      )}
    </div>
  )
}

/** Source → … → sink for one finding, built from report.leak_paths. */
export function LeakPathChain({
  report,
  finding,
  current,
  onJump,
}: {
  report: Report
  finding: Finding
  current?: string
  onJump?: (eventId: string) => void
}) {
  const path = (report.leak_paths ?? []).find(
    (p) => p.data_type === finding.data_type && p.steps.some((s) => s.event_id === finding.event_id && s.kind === "leak"),
  )
  if (!path) {
    return <p className="mt-2 text-[11px] text-muted-foreground">No recorded entry point for this value: it first appears on an emission channel.</p>
  }
  const steps = dedupeSteps(path.steps)
  return (
    <ol className="mt-2 flex flex-wrap items-center gap-1 text-[11px]" aria-label="Leak path from source to sink">
      {steps.map((s, i) => (
        <li key={`${s.event_id}-${s.kind}`} className="inline-flex items-center gap-1">
          {i > 0 && <ArrowRight className="size-3 text-muted-foreground" aria-hidden />}
          <button
            type="button"
            disabled={!onJump}
            onClick={() => onJump?.(s.event_id)}
            className={cn(
              "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              s.kind === "source" ? "border-dashed border-border text-muted-foreground" : "border-foreground/30",
              s.event_id === current && "bg-foreground text-background",
            )}
            title={`${s.event_id}: ${s.source} → ${s.target}`}
          >
            <span className="font-sans">{s.kind === "source" ? "entered" : "leaked"}</span> {s.channel}
          </button>
        </li>
      ))}
    </ol>
  )
}
