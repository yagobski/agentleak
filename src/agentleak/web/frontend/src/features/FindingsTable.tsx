// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useEffect, useMemo, useState } from "react"
import { ArrowRight, Search } from "lucide-react"
import type { Finding, Report, TriageItem, TriageStateOrNone, TriageView } from "@/lib/api"
import { TRIAGE_META, TRIAGE_STATES, provenanceText, triageText } from "@/lib/triage"
import { cn } from "@/lib/utils"
import { DataTable, type Column } from "@/components/DataTable"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { CopyLinkButton, LevelChip } from "./Chips"
import { LeakPathChain } from "./TraceExplorer"
import { TriageChip, TriageDetail, TriageDialog, type DecisionInput } from "./Triage"

export interface TriageBinding {
  view: TriageView | null
  error?: string
  decide: (d: DecisionInput) => Promise<void>
}

type TriageFilter = "all" | TriageStateOrNone | "expired"

export function FindingsTable({
  report,
  runId,
  activeFinding,
  onActivate,
  onShowEvent,
  triage,
}: {
  report: Report
  /** Stored run id: enables per-finding permalinks. */
  runId?: string
  /** Triage of a stored run; absent for an unsaved analysis. */
  triage?: TriageBinding
  activeFinding: string | null
  onActivate: (findingId: string | null) => void
  onShowEvent: (eventId: string) => void
}) {
  const [q, setQ] = useState("")
  const [levels, setLevels] = useState<Set<number>>(new Set())
  const [channel, setChannel] = useState("all")
  const [tstate, setTstate] = useState<TriageFilter>("all")
  const [selected, setSelected] = useState<string[]>([])
  const [dialog, setDialog] = useState<{ ids: string[]; initial?: TriageItem } | null>(null)
  const byId = useMemo(() => {
    const m = new Map<string, TriageItem>()
    triage?.view?.findings.forEach((t) => m.set(t.finding_id, t))
    return m
  }, [triage?.view])
  const tcount = (s: TriageFilter) =>
    report.findings.filter((f) => {
      const t = byId.get(f.finding_id)
      if (s === "expired") return !!t?.expired
      return (t?.effective_state ?? "untriaged") === s
    }).length

  // A permalink to a finding opens with that row in view.
  useEffect(() => {
    if (!activeFinding) return
    const t = window.setTimeout(() => document.getElementById(`row-${activeFinding}`)?.scrollIntoView({ block: "center" }), 60)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const channels = useMemo(() => Array.from(new Set(report.findings.map((f) => f.channel))).sort(), [report.findings])
  const levelCounts = useMemo(() => {
    const m: Record<number, number> = {}
    report.findings.forEach((f) => (m[f.level] = (m[f.level] ?? 0) + 1))
    return m
  }, [report.findings])

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase()
    return report.findings.filter((f) => {
      if (levels.size && !levels.has(f.level)) return false
      if (channel !== "all" && f.channel !== channel) return false
      if (tstate !== "all") {
        const t = byId.get(f.finding_id)
        if (tstate === "expired" ? !t?.expired : (t?.effective_state ?? "untriaged") !== tstate) return false
      }
      if (needle) {
        const hay = `${f.finding_id} ${f.data_type} ${f.channel} ${f.detector} ${f.redacted_value} ${f.source} ${f.target} ${f.event_id ?? ""}`.toLowerCase()
        if (!hay.includes(needle)) return false
      }
      return true
    })
  }, [report.findings, q, levels, channel, tstate, byId])

  const iso = (epoch?: number | null) => (epoch ? new Date(epoch * 1000).toISOString() : "")
  const triageColumns: Column<Finding>[] = triage
    ? [
        {
          id: "triage",
          header: "Triage",
          value: (f) => byId.get(f.finding_id)?.effective_state ?? "untriaged",
          cell: (f) => <TriageChip item={byId.get(f.finding_id)} />,
        },
        { id: "triage_text", header: "", exportOnly: true, value: (f) => triageText(byId.get(f.finding_id)) },
        { id: "triage_recorded_state", header: "", exportOnly: true, value: (f) => byId.get(f.finding_id)?.state ?? "untriaged" },
        { id: "triage_rationale", header: "", exportOnly: true, value: (f) => byId.get(f.finding_id)?.decision?.rationale ?? "" },
        { id: "triage_reviewer", header: "", exportOnly: true, value: (f) => byId.get(f.finding_id)?.decision?.reviewer_email ?? "" },
        { id: "triage_decided_at", header: "", exportOnly: true, value: (f) => iso(byId.get(f.finding_id)?.decision?.created_at) },
        { id: "triage_expires_on", header: "", exportOnly: true, value: (f) => byId.get(f.finding_id)?.decision?.expires_on ?? "" },
        { id: "triage_source", header: "", exportOnly: true, value: (f) => provenanceText(byId.get(f.finding_id)) ?? "" },
        { id: "triage_identity", header: "", exportOnly: true, value: (f) => byId.get(f.finding_id)?.identity ?? "" },
      ]
    : []

  const columns: Column<Finding>[] = [
    { id: "level", header: "Level", value: (f) => f.level, cell: (f) => <LevelChip level={f.level} /> },
    ...triageColumns.slice(0, 1),
    { id: "channel", header: "Channel", value: (f) => f.channel, cell: (f) => <code className="font-mono text-[12px]">{f.channel}</code> },
    {
      id: "data_type",
      header: "Data type",
      value: (f) => f.data_type,
      className: "break-words",
      cell: (f) => (
        <button
          type="button"
          aria-expanded={activeFinding === f.finding_id}
          title="Show recommendation and leak path"
          onClick={(e) => {
            e.stopPropagation()
            onActivate(activeFinding === f.finding_id ? null : f.finding_id)
          }}
          className="rounded-sm text-left underline decoration-border underline-offset-2 hover:decoration-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {f.data_type}
        </button>
      ),
    },
    {
      id: "masked_value",
      header: "Value (masked)",
      value: (f) => f.redacted_value,
      cell: (f) => <code className="break-all font-mono text-[12px]">{f.redacted_value}</code>,
      sortable: false,
    },
    {
      id: "path",
      header: "Source → target",
      value: (f) => `${f.source} -> ${f.target}`,
      hideBelow: "md",
      cell: (f) => (
        <span className="inline-flex max-w-[16rem] items-center gap-1 text-[12px] text-muted-foreground">
          <span className="truncate">{f.source}</span>
          <ArrowRight className="size-3 shrink-0" aria-label="to" />
          <span className="truncate">{f.target}</span>
        </span>
      ),
    },
    {
      id: "event_id",
      header: "Event",
      value: (f) => f.event_id ?? "",
      cell: (f) =>
        f.event_id ? (
          <button
            type="button"
            className="rounded-sm font-mono text-[12px] underline decoration-border underline-offset-2 hover:decoration-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={(e) => {
              e.stopPropagation()
              onShowEvent(f.event_id!)
            }}
            title="Show this event in the trace"
          >
            {f.event_id}
          </button>
        ) : (
          "–"
        ),
    },
    { id: "detector", header: "Detector", value: (f) => f.detector, hideBelow: "lg", cell: (f) => <span className="text-[12px] text-muted-foreground">{f.detector}</span> },
    { id: "confidence", header: "Conf.", value: (f) => f.confidence, align: "right", hideBelow: "lg", cell: (f) => <span className="font-mono text-[12px]">{f.confidence.toFixed(2)}</span> },
    { id: "finding_id", header: "Id", value: (f) => f.finding_id, hideBelow: "lg", cell: (f) => <span className="font-mono text-[11px] text-muted-foreground">{f.finding_id}</span> },
    ...triageColumns.slice(1),
    ...(runId
      ? [
          {
            id: "link",
            header: "",
            value: () => "",
            sortable: false,
            exportable: false,
            cell: (f: Finding) => <CopyLinkButton path={`/runs/${runId}?tab=findings&finding=${encodeURIComponent(f.finding_id)}`} label="Link" />,
          } satisfies Column<Finding>,
        ]
      : []),
  ]

  if (!report.findings.length) {
    return (
      <p className="px-4 py-10 text-center text-sm text-muted-foreground">
        No finding from the enabled deterministic detectors (tiers that ran:{" "}
        {report.detection?.tiers.join(", ") || "not recorded"}).
      </p>
    )
  }

  function toggleLevel(l: number) {
    setLevels((s) => {
      const n = new Set(s)
      if (n.has(l)) n.delete(l)
      else n.add(l)
      return n
    })
  }

  const triageReady = !!(triage && triage.view && runId)
  return (
    <>
    {triage?.error && (
      <p role="alert" className="border-b border-border px-4 py-2 text-[13px] text-sev-l4">
        Triage could not be loaded: {triage.error}
      </p>
    )}
    {triageReady && selected.length > 0 && (
      <div className="flex flex-wrap items-center gap-2 border-b border-border bg-muted/40 px-4 py-2 text-[13px]" role="region" aria-label="Bulk triage">
        <span className="tnum">
          {selected.length} of {report.findings.length} selected
        </span>
        <Button size="sm" className="h-7" onClick={() => setDialog({ ids: selected })}>
          Triage selected
        </Button>
        <Button size="sm" variant="ghost" className="h-7" onClick={() => setSelected([])}>
          Clear selection
        </Button>
      </div>
    )}
    <DataTable
      caption="Leaked findings"
      columns={columns}
      rows={rows}
      rowKey={(f) => f.finding_id}
      initialSort={{ id: "level", dir: "desc" }}
      exportName={`findings-${report.run_id}`}
      activeKey={activeFinding}
      pageSize={100}
      onRowClick={(f) => onActivate(activeFinding === f.finding_id ? null : f.finding_id)}
      selection={triageReady ? { selected, onChange: setSelected, label: (f) => `${f.finding_id} ${f.data_type}` } : undefined}
      expanded={(f) =>
        f.finding_id === activeFinding ? (
          <div className="space-y-2 text-[13px]">
            <p>
              <span className="text-muted-foreground">Recommendation. </span>
              {f.recommendation}
            </p>
            <LeakPathChain report={report} finding={f} current={f.event_id} onJump={onShowEvent} />
            {triageReady && (
              <TriageDetail
                runId={runId!}
                finding={f}
                item={byId.get(f.finding_id)}
                onEdit={() => setDialog({ ids: [f.finding_id], initial: byId.get(f.finding_id) })}
              />
            )}
          </div>
        ) : null
      }
      empty="No finding matches these filters."
      toolbar={
        <>
          <div className="relative min-w-[160px] flex-1 sm:max-w-[16rem]">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Type, value, actor, event"
              aria-label="Search findings"
              data-shortcut="search"
              className="h-8 pl-8 text-[13px]"
            />
          </div>
          <label className="sr-only" htmlFor="findings-channel">
            Channel
          </label>
          <select
            id="findings-channel"
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
            className="h-8 rounded-md border border-input bg-background px-2 text-[13px]"
          >
            <option value="all">All channels</option>
            {channels.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <div className="flex items-center gap-1" role="group" aria-label="Severity levels">
            {[4, 3, 2, 1].map((l) => {
              const n = levelCounts[l] ?? 0
              const on = levels.has(l)
              return (
                <button
                  key={l}
                  type="button"
                  disabled={n === 0}
                  aria-pressed={on}
                  onClick={() => toggleLevel(l)}
                  className={cn(
                    "rounded border px-1.5 py-0.5 font-mono text-[11px] disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    on ? "border-foreground bg-foreground text-background" : "border-border text-muted-foreground hover:text-foreground",
                  )}
                >
                  L{l} <span className="tnum">{n}</span>
                </button>
              )
            })}
          </div>
          {triageReady && (
            <>
              <label className="sr-only" htmlFor="findings-triage">
                Triage state
              </label>
              <select
                id="findings-triage"
                value={tstate}
                onChange={(e) => setTstate(e.target.value as TriageFilter)}
                className="h-8 rounded-md border border-input bg-background px-2 text-[13px]"
              >
                <option value="all">All triage states</option>
                {(["untriaged", ...TRIAGE_STATES] as TriageStateOrNone[]).map((s) => (
                  <option key={s} value={s}>
                    {TRIAGE_META[s].label} ({tcount(s)})
                  </option>
                ))}
                <option value="expired">Expired accepted risk ({tcount("expired")})</option>
              </select>
            </>
          )}
        </>
      }
    />
    {dialog && triage && (
      <TriageDialog
        open
        onOpenChange={(v) => !v && setDialog(null)}
        findingIds={dialog.ids}
        initial={dialog.initial}
        onSubmit={async (d) => {
          await triage.decide(d)
          if (dialog.ids.length > 1) setSelected([])
        }}
      />
    )}
    </>
  )
}
