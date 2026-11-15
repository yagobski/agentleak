// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useMemo, useState } from "react"
import { ArrowRight, Search } from "lucide-react"
import type { Finding, Report } from "@/lib/api"
import { cn } from "@/lib/utils"
import { DataTable, type Column } from "@/components/DataTable"
import { Input } from "@/components/ui/input"
import { CopyLinkButton, LevelChip } from "./Chips"
import { LeakPathChain } from "./TraceExplorer"

export function FindingsTable({
  report,
  runId,
  activeFinding,
  onActivate,
  onShowEvent,
}: {
  report: Report
  /** Stored run id: enables per-finding permalinks. */
  runId?: string
  activeFinding: string | null
  onActivate: (findingId: string | null) => void
  onShowEvent: (eventId: string) => void
}) {
  const [q, setQ] = useState("")
  const [levels, setLevels] = useState<Set<number>>(new Set())
  const [channel, setChannel] = useState("all")

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
      if (needle) {
        const hay = `${f.finding_id} ${f.data_type} ${f.channel} ${f.detector} ${f.redacted_value} ${f.source} ${f.target} ${f.event_id ?? ""}`.toLowerCase()
        if (!hay.includes(needle)) return false
      }
      return true
    })
  }, [report.findings, q, levels, channel])

  const columns: Column<Finding>[] = [
    { id: "level", header: "Level", value: (f) => f.level, cell: (f) => <LevelChip level={f.level} /> },
    { id: "channel", header: "Channel", value: (f) => f.channel, cell: (f) => <code className="font-mono text-[12px]">{f.channel}</code> },
    { id: "data_type", header: "Data type", value: (f) => f.data_type, className: "break-words" },
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

  return (
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
      expanded={(f) =>
        f.finding_id === activeFinding ? (
          <div className="space-y-2 text-[13px]">
            <p>
              <span className="text-muted-foreground">Recommendation. </span>
              {f.recommendation}
            </p>
            <LeakPathChain report={report} finding={f} current={f.event_id} onJump={onShowEvent} />
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
        </>
      }
    />
  )
}
