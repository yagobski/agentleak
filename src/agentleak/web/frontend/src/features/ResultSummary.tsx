// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useMemo, useState } from "react"
import { ChevronRight } from "lucide-react"
import type { LevelLabel, Report, TraceDoc } from "@/lib/api"
import { channelSplit, useMeta, type ChannelSplit } from "@/lib/meta"
import { cn } from "@/lib/utils"
import { LevelChip, VerdictLabel } from "./Chips"

export interface ChannelRow {
  channel: string
  events: number | null
  findings: number
  maxLevel: number
  ri: number
}

/** Per-channel event counts: from the trace when we have it, else from the report's flow edges. */
export function channelEventCounts(report: Report, trace?: TraceDoc | null): Record<string, number> | null {
  if (trace?.events?.length) {
    const m: Record<string, number> = {}
    for (const e of trace.events) m[e.channel] = (m[e.channel] ?? 0) + 1
    return m
  }
  const edges = report.flow?.edges
  if (!edges?.length) return null
  const m: Record<string, number> = {}
  for (const e of edges) m[e.channel] = (m[e.channel] ?? 0) + e.count
  return m
}

export function channelRows(report: Report, split: ChannelSplit, trace?: TraceDoc | null): ChannelRow[] {
  const counts = channelEventCounts(report, trace)
  const extra = report.channel_risks.map((c) => c.channel).filter((c) => !split.all.includes(c))
  const emissions = [...split.emissions, ...extra]
  // final_output first: it is the channel an output-only audit would look at.
  emissions.sort((a, b) => (a === "final_output" ? -1 : b === "final_output" ? 1 : 0))
  return emissions.map((channel) => {
    const fs = report.findings.filter((f) => f.channel === channel)
    return {
      channel,
      events: counts ? counts[channel] ?? 0 : null,
      findings: fs.length,
      maxLevel: fs.reduce((m, f) => Math.max(m, f.level), 0),
      ri: report.channel_risks.find((c) => c.channel === channel)?.ri ?? 0,
    }
  })
}

/** The sentence that states the product's thesis for this run, with its denominator. */
export function headline(report: Report, rows: ChannelRow[]): { text: string; tone: "leak" | "contrast" | "clean" } {
  const final = rows.find((r) => r.channel === "final_output")
  const internal = rows.filter((r) => r.channel !== "final_output")
  const present = internal.filter((r) => r.events === null || r.events > 0)
  const leaking = internal.filter((r) => r.findings > 0)
  const tier = report.detection ? `${report.detection.mode} tier` : "enabled detectors"
  if (!report.findings.length) {
    return {
      text: `No finding from the enabled deterministic detectors on any emission channel (${tier}). This is not proof that nothing leaked: data the detectors do not recognise is not reported.`,
      tone: "clean",
    }
  }
  const denom = `${leaking.length} of ${present.length} internal channel${present.length === 1 ? "" : "s"} in this trace`
  if (final && final.findings === 0) {
    const finalNote = final.events === 0 ? "The trace has no final answer" : "The final answer has no finding"
    return { text: `${finalNote}, but ${denom} disclosed sensitive data. An output-only audit would miss these.`, tone: "contrast" }
  }
  return {
    text: `The final answer leaked (L${final?.maxLevel ?? "?"}), and so did ${denom}.`,
    tone: "leak",
  }
}

export function ChannelVerdicts({
  report,
  trace,
  onSelectChannel,
}: {
  report: Report
  trace?: TraceDoc | null
  onSelectChannel?: (channel: string) => void
}) {
  const meta = useMeta()
  const split = channelSplit(meta)
  const rows = useMemo(() => channelRows(report, split, trace), [report, split, trace])
  const counts = channelEventCounts(report, trace)
  const head = headline(report, rows)
  const maxRi = Math.max(...rows.map((r) => r.ri), 0.0001)

  return (
    <section aria-labelledby="channel-verdicts" className="min-w-0">
      <p
        className={cn(
          "mb-3 max-w-3xl text-[15px] leading-relaxed",
          head.tone === "clean" ? "text-foreground" : "text-foreground",
        )}
      >
        {head.text}
      </p>
      <h3 id="channel-verdicts" className="sr-only">
        Result per emission channel
      </h3>
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-sm">
          <caption className="sr-only">Findings per emission channel</caption>
          <thead>
            <tr className="border-b border-border text-left text-[11px] text-muted-foreground">
              <th scope="col" className="px-4 py-2 font-medium">Emission channel</th>
              <th scope="col" className="px-3 py-2 font-medium">Result</th>
              <th scope="col" className="hidden px-3 py-2 text-right font-medium sm:table-cell">Events</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">Findings</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">
                <abbr title="Channel Risk Index: weighted severity of the secrets disclosed on this channel, over ρ_S">RI</abbr>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const absent = r.events === 0
              return (
                <tr
                  key={r.channel}
                  className={cn("border-b border-border/70 last:border-b-0", r.channel === "final_output" && "bg-muted/40")}
                >
                  <td className="px-4 py-2">
                    {onSelectChannel && !absent ? (
                      <button
                        type="button"
                        className="rounded-sm font-mono text-[13px] underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        onClick={() => onSelectChannel(r.channel)}
                      >
                        {r.channel}
                      </button>
                    ) : (
                      <span className={cn("font-mono text-[13px]", absent && "text-muted-foreground")}>{r.channel}</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {r.findings > 0 ? (
                      <span className="inline-flex items-center gap-2">
                        <LevelChip level={r.maxLevel} />
                        <span>leaked</span>
                      </span>
                    ) : absent ? (
                      <span className="text-muted-foreground">not in trace</span>
                    ) : (
                      <span className="text-sev-ok">no finding</span>
                    )}
                  </td>
                  <td className="hidden px-3 py-2 text-right font-mono tnum text-muted-foreground sm:table-cell">
                    {r.events ?? "–"}
                  </td>
                  <td className="px-3 py-2 text-right font-mono tnum">{r.findings}</td>
                  <td className="px-4 py-2">
                    <div className="flex items-center justify-end gap-2">
                      <div className="hidden h-1.5 w-20 overflow-hidden rounded-full bg-muted md:block" aria-hidden>
                        <div className="h-full rounded-full bg-foreground/70" style={{ width: `${(r.ri / maxRi) * 100}%` }} />
                      </div>
                      <span className="w-12 text-right font-mono tnum">{r.ri.toFixed(3)}</span>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {counts && (
        <p className="mt-2 text-[12px] text-muted-foreground">
          Source channels, not scored as leaks:{" "}
          {split.sources.map((c, i) => (
            <span key={c}>
              {i > 0 && ", "}
              <code className="font-mono">{c}</code> <span className="tnum">{counts[c] ?? 0}</span> event{(counts[c] ?? 0) === 1 ? "" : "s"}
            </span>
          ))}
          . Data arriving there forms the vault (ρ_S).
        </p>
      )}
    </section>
  )
}

const LEVELS: LevelLabel[] = ["L4", "L3", "L2", "L1"]

/** Score block plus the AgentRisk derivation, read entirely from the report. */
export function ScorePanel({ report }: { report: Report }) {
  const [open, setOpen] = useState(false)
  const ar = report.agentrisk
  const weights = ar?.weights
  const leaked = ar?.level_profile ?? report.summary.level_profile
  const vault = ar?.vault_level_profile ?? report.summary.vault_level_profile
  const w = (label: LevelLabel) => (weights ? weights[Number(label.slice(1)) - 1] : undefined)
  const wslCheck = weights ? LEVELS.reduce((s, l) => s + (leaked[l] ?? 0) * (w(l) ?? 0), 0) : null
  const rhoCheck = weights ? LEVELS.reduce((s, l) => s + (vault[l] ?? 0) * (w(l) ?? 0), 0) : null
  const riCheck = report.rho_s > 0 ? report.wsl / report.rho_s : 0
  const scoreCheck = Math.round(100 * (1 - report.risk_index))
  const policy = report.privacy_policy

  return (
    <section aria-label="AgentRisk score" className="min-w-0">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4 xl:grid-cols-3">
        <div className="col-span-2 sm:col-span-1 xl:col-span-3">
          <dt className="text-[11px] text-muted-foreground">Risk Index (RI)</dt>
          <dd className="mt-0.5 font-mono text-3xl font-medium leading-none tnum">{report.risk_index.toFixed(3)}</dd>
          <dd className="mt-1.5">
            <VerdictLabel verdict={report.verdict} />
          </dd>
        </div>
        <div>
          <dt className="text-[11px] text-muted-foreground">Leaked / vault</dt>
          <dd className="mt-0.5 font-mono text-xl leading-none tnum">
            {report.summary.leaked_secrets}
            <span className="text-muted-foreground"> / {report.summary.vault_secrets}</span>
          </dd>
          <dd className="mt-1 text-[11px] text-muted-foreground">distinct values</dd>
        </div>
        <div>
          <dt className="text-[11px] text-muted-foreground">WSL / ρ_S</dt>
          <dd className="mt-0.5 font-mono text-xl leading-none tnum">
            {report.wsl}
            <span className="text-muted-foreground"> / {report.rho_s}</span>
          </dd>
          <dd className="mt-1 text-[11px] text-muted-foreground">severity-weighted</dd>
        </div>
        <div>
          <dt className="text-[11px] text-muted-foreground">Privacy score</dt>
          <dd className="mt-0.5 font-mono text-xl leading-none tnum">
            {report.privacy_score}
            <span className="text-muted-foreground"> / 100</span>
          </dd>
          <dd className="mt-1 text-[11px] text-muted-foreground">
            {report.blocked ? <span className="font-medium text-sev-l4">blocked by gate</span> : "not blocked"}
          </dd>
        </div>
      </dl>

      <button
        type="button"
        aria-expanded={open}
        aria-controls="score-derivation"
        onClick={() => setOpen((o) => !o)}
        className="mt-4 inline-flex items-center gap-1 rounded-sm text-[12px] text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ChevronRight className={cn("size-3.5 transition-transform motion-reduce:transition-none", open && "rotate-90")} />
        How this number is computed
      </button>

      {open && (
        <div id="score-derivation" className="mt-3 space-y-3 rounded-md border border-border p-4 text-[13px]">
          <div className="overflow-x-auto">
            <table className="w-full max-w-xl font-mono text-[12px] tnum">
              <caption className="sr-only">AgentRisk derivation by severity level</caption>
              <thead>
                <tr className="border-b border-border text-left font-sans text-[11px] text-muted-foreground">
                  <th scope="col" className="py-1.5 pr-3 font-medium">Level</th>
                  <th scope="col" className="py-1.5 pr-3 text-right font-medium">Weight w</th>
                  <th scope="col" className="py-1.5 pr-3 text-right font-medium">Leaked</th>
                  <th scope="col" className="py-1.5 pr-3 text-right font-medium">In vault</th>
                  <th scope="col" className="py-1.5 pr-3 text-right font-medium">w × leaked</th>
                  <th scope="col" className="py-1.5 text-right font-medium">w × vault</th>
                </tr>
              </thead>
              <tbody>
                {LEVELS.map((l) => (
                  <tr key={l} className="border-b border-border/60">
                    <td className="py-1 pr-3">{l}</td>
                    <td className="py-1 pr-3 text-right">{w(l) ?? "–"}</td>
                    <td className="py-1 pr-3 text-right">{leaked[l] ?? 0}</td>
                    <td className="py-1 pr-3 text-right">{vault[l] ?? 0}</td>
                    <td className="py-1 pr-3 text-right">{w(l) !== undefined ? (leaked[l] ?? 0) * w(l)! : "–"}</td>
                    <td className="py-1 text-right">{w(l) !== undefined ? (vault[l] ?? 0) * w(l)! : "–"}</td>
                  </tr>
                ))}
                <tr className="font-medium">
                  <td className="py-1 pr-3 font-sans" colSpan={4}>
                    Sum
                  </td>
                  <td className="py-1 pr-3 text-right">WSL {report.wsl}</td>
                  <td className="py-1 text-right">ρ_S {report.rho_s}</td>
                </tr>
              </tbody>
            </table>
          </div>
          {weights && (wslCheck !== report.wsl || rhoCheck !== report.rho_s) && (
            <p className="text-sev-l2">
              The per-level sums ({wslCheck}, {rhoCheck}) differ from the reported WSL and ρ_S; the vault was probably
              given as a raw ρ_S. The reported values are the ones used.
            </p>
          )}
          <dl className="grid gap-x-4 gap-y-1.5 sm:grid-cols-[max-content_1fr]">
            <dt className="text-muted-foreground">Risk Index</dt>
            <dd className="font-mono tnum">
              RI = WSL / ρ_S = {report.wsl} / {report.rho_s} = {riCheck.toFixed(4)}
              {Math.abs(riCheck - report.risk_index) > 0.0006 && (
                <span className="font-sans text-sev-l2"> (reported {report.risk_index})</span>
              )}
            </dd>
            <dt className="text-muted-foreground">Privacy score</dt>
            <dd className="font-mono tnum">
              round(100 × (1 − {report.risk_index})) = {scoreCheck}
              {scoreCheck !== report.privacy_score && <span className="font-sans text-sev-l2"> (reported {report.privacy_score})</span>}
            </dd>
            <dt className="text-muted-foreground">Vault scope (ρ_S)</dt>
            <dd>{report.scope_def}</dd>
            <dt className="text-muted-foreground">Counting rule</dt>
            <dd>Distinct secrets, not occurrences: a value disclosed on three channels counts once in WSL.</dd>
            <dt className="text-muted-foreground">Verdict</dt>
            <dd>
              <VerdictLabel verdict={report.verdict} className="text-[13px]" /> as returned by the engine.
            </dd>
            <dt className="text-muted-foreground">Gate</dt>
            <dd>
              {report.blocked ? "Blocked. " : "Not blocked. "}
              {policy?.enabled
                ? policy.passed
                  ? `Privacy policy passed (${policy.assertions_checked.length} assertion${policy.assertions_checked.length === 1 ? "" : "s"} checked).`
                  : `Privacy policy failed: ${policy.violations.length} violation${policy.violations.length === 1 ? "" : "s"}.`
                : "No privacy policy was attached to this analysis."}
            </dd>
            {ar?.detectors && (
              <>
                <dt className="text-muted-foreground">Detectors with matches</dt>
                <dd className="font-mono text-[12px]">{ar.detectors.join(", ") || "none"}</dd>
              </>
            )}
          </dl>
          <p className="text-[12px] text-muted-foreground">
            Weights, profiles and totals are read from this report's <code className="font-mono">agentrisk</code> block.
            Reference: docs/scoring.md.
          </p>
        </div>
      )}
    </section>
  )
}
