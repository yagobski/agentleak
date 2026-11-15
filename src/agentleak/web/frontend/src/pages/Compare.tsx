// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useEffect, useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { ArrowLeftRight, TriangleAlert } from "lucide-react"
import { api, type Finding, type LevelLabel, type Run } from "@/lib/api"
import { channelSplit, useMeta } from "@/lib/meta"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { DataTable, type Column } from "@/components/DataTable"
import { DetectionBadge, LevelChip, VerdictLabel } from "@/features/Chips"
import { formatStamp, useAllRuns, type RunRow } from "@/features/RunsTable"
import { PageHeader } from "@/layout/AppShell"

type Status = "resolved" | "added" | "unchanged"
interface DiffRow {
  key: string
  status: Status
  finding: Finding
}

/**
 * Reports carry no stable finding fingerprint (finding ids are per run), so a
 * finding is matched on what identifies the disclosure: channel, data type,
 * level and masked value.
 */
function fingerprint(f: Finding) {
  return `${f.channel}|${f.data_type}|${f.level}|${f.redacted_value}`
}

function diffFindings(a: Finding[], b: Finding[]): DiffRow[] {
  const bucket = (fs: Finding[]) => {
    const m = new Map<string, Finding[]>()
    fs.forEach((f) => m.set(fingerprint(f), [...(m.get(fingerprint(f)) ?? []), f]))
    return m
  }
  const ma = bucket(a)
  const mb = bucket(b)
  const out: DiffRow[] = []
  for (const key of new Set([...ma.keys(), ...mb.keys()])) {
    const xa = ma.get(key) ?? []
    const xb = mb.get(key) ?? []
    const shared = Math.min(xa.length, xb.length)
    for (let i = 0; i < shared; i++) out.push({ key: `${key}#u${i}`, status: "unchanged", finding: xb[i] })
    for (let i = shared; i < xa.length; i++) out.push({ key: `${key}#r${i}`, status: "resolved", finding: xa[i] })
    for (let i = shared; i < xb.length; i++) out.push({ key: `${key}#a${i}`, status: "added", finding: xb[i] })
  }
  return out
}

function signed(n: number, digits = 3) {
  if (Math.abs(n) < 10 ** -(digits + 1)) return (0).toFixed(digits)
  return `${n > 0 ? "+" : "−"}${Math.abs(n).toFixed(digits)}`
}

function runLabel(r: RunRow) {
  return `${r.id} · ${r.project_name ?? ""} · ${r.agent_name}${r.label ? ` (${r.label})` : ""} · ${formatStamp(r.created_at)}`
}

const LEVELS: LevelLabel[] = ["L4", "L3", "L2", "L1"]

export function Compare() {
  const [params, setParams] = useSearchParams()
  const a = params.get("a") ?? ""
  const b = params.get("b") ?? ""
  const { runs } = useAllRuns()
  const meta = useMeta()
  const split = channelSplit(meta)
  const [data, setData] = useState<{ a: Run; b: Run; dominance: "a" | "b" | "neither"; comparable?: boolean; reason?: string } | null>(null)
  const [error, setError] = useState("")
  const [statusFilter, setStatusFilter] = useState<Status | "all">("all")

  useEffect(() => {
    setData(null)
    setError("")
    if (!a || !b) return
    if (a === b) {
      setError("Pick two different runs.")
      return
    }
    api
      .compare(a, b)
      .then(setData)
      .catch((e) => setError((e as Error).message))
  }, [a, b])

  function pick(which: "a" | "b", id: string) {
    setParams((p) => {
      const n = new URLSearchParams(p)
      if (id) n.set(which, id)
      else n.delete(which)
      return n
    })
  }

  const diff = useMemo(() => (data ? diffFindings(data.a.report.findings, data.b.report.findings) : []), [data])
  const counts = useMemo(() => {
    const c = { resolved: 0, added: 0, unchanged: 0 }
    diff.forEach((d) => c[d.status]++)
    return c
  }, [diff])

  const channels = useMemo(() => {
    if (!data) return []
    const ra = data.a.report
    const rb = data.b.report
    const extra = [...ra.channel_risks, ...rb.channel_risks].map((c) => c.channel).filter((c) => !split.emissions.includes(c))
    return [...split.emissions, ...new Set(extra)].map((ch) => {
      const riA = ra.channel_risks.find((c) => c.channel === ch)?.ri ?? 0
      const riB = rb.channel_risks.find((c) => c.channel === ch)?.ri ?? 0
      return {
        channel: ch,
        riA,
        riB,
        fA: ra.findings.filter((f) => f.channel === ch).length,
        fB: rb.findings.filter((f) => f.channel === ch).length,
      }
    })
  }, [data, split.emissions])

  const diffColumns: Column<DiffRow>[] = [
    {
      id: "status",
      header: "Change",
      value: (d) => d.status,
      cell: (d) => (
        <span className={cn("text-[12px] font-medium", d.status === "added" && "text-sev-l4", d.status === "resolved" && "text-sev-ok", d.status === "unchanged" && "text-muted-foreground")}>
          {d.status}
        </span>
      ),
    },
    { id: "level", header: "Level", value: (d) => d.finding.level, cell: (d) => <LevelChip level={d.finding.level} /> },
    { id: "channel", header: "Channel", value: (d) => d.finding.channel, cell: (d) => <code className="font-mono text-[12px]">{d.finding.channel}</code> },
    { id: "data_type", header: "Data type", value: (d) => d.finding.data_type },
    { id: "masked_value", header: "Value (masked)", value: (d) => d.finding.redacted_value, cell: (d) => <code className="break-all font-mono text-[12px]">{d.finding.redacted_value}</code> },
    { id: "run", header: "Seen in", value: (d) => (d.status === "resolved" ? "A" : d.status === "added" ? "B" : "A and B"), hideBelow: "sm" },
  ]

  const ra = data?.a.report
  const rb = data?.b.report
  const tiersDiffer = ra && rb && JSON.stringify(ra.detection ?? null) !== JSON.stringify(rb.detection ?? null)

  return (
    <div className="min-w-0">
      <PageHeader
        title="Compare runs"
        crumbs={[{ label: "Runs", to: "/runs" }, { label: "Compare" }]}
        description="A is the baseline, B the candidate. Use it to check whether a mitigation removed the leaks it targeted without adding new ones."
      />

      <div className="mb-6 grid items-end gap-3 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
        {(["a", "b"] as const).map((which, i) => (
          <div key={which} className={cn("min-w-0", i === 1 && "md:order-3")}>
            <label className="block text-[12px] text-muted-foreground" htmlFor={`pick-${which}`}>
              {which === "a" ? "A, baseline" : "B, candidate"}
            </label>
            <select
              id={`pick-${which}`}
              value={which === "a" ? a : b}
              onChange={(e) => pick(which, e.target.value)}
              className="mt-1 h-9 w-full min-w-0 rounded-md border border-input bg-background px-2 font-mono text-[12px]"
            >
              <option value="">Choose a run…</option>
              {(runs ?? []).map((r) => (
                <option key={r.id} value={r.id}>
                  {runLabel(r)}
                </option>
              ))}
            </select>
          </div>
        ))}
        <Button
          variant="outline"
          size="icon"
          className="md:order-2"
          aria-label="Swap A and B"
          disabled={!a || !b}
          onClick={() => setParams(new URLSearchParams({ a: b, b: a }))}
        >
          <ArrowLeftRight />
        </Button>
      </div>

      {!a || !b ? (
        <p className="text-sm text-muted-foreground">
          Choose two runs above, or tick two rows on the <Link className="underline underline-offset-2" to="/runs">Runs</Link> page.
          Comparisons are most meaningful between runs of the same scenario before and after a change.
        </p>
      ) : error ? (
        <p role="alert" className="text-sm text-sev-l4">{error}</p>
      ) : !data || !ra || !rb ? (
        <div className="h-48 rounded-lg bg-muted motion-safe:animate-pulse" aria-busy="true" />
      ) : (
        <div className="space-y-6">
          {/* headline */}
          <section className="rounded-lg border border-border bg-card p-4 sm:p-5">
            <p className="max-w-3xl text-[15px] leading-relaxed">
              Risk Index <span className="font-mono tnum">{ra.risk_index.toFixed(3)}</span> →{" "}
              <span className="font-mono tnum">{rb.risk_index.toFixed(3)}</span> ({signed(rb.risk_index - ra.risk_index)}).{" "}
              {counts.resolved} finding{counts.resolved === 1 ? "" : "s"} resolved, {counts.added} added, {counts.unchanged} unchanged.{" "}
              {rb.findings.length === 0 && ra.findings.length > 0
                ? "B has no finding from the enabled deterministic detectors."
                : null}
            </p>
            {data.comparable === false ? (
              <p className="mt-3 flex gap-2 text-[13px] text-sev-l2">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span>Scores are not on the same denominator, so the RI delta is not a like-for-like comparison. {data.reason}</span>
              </p>
            ) : (
              <p className="mt-2 text-[13px] text-muted-foreground">
                {data.dominance === "a"
                  ? "A leaks at least as many secrets as B at every severity level and more at one, so B ranks lower-risk under any positive severity weights."
                  : data.dominance === "b"
                    ? "B leaks at least as many secrets as A at every severity level and more at one, so B ranks higher-risk under any positive severity weights."
                    : "Neither run dominates the other level by level: which one is riskier depends on the severity weights."}{" "}
                Same vault scope (ρ_S {ra.rho_s}).
              </p>
            )}
            {tiersDiffer && (
              <p className="mt-2 flex gap-2 text-[13px] text-sev-l2">
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
                The two runs used different detector tiers; a finding missing from one may be a detection difference, not a fix.
              </p>
            )}

            <div className="mt-4 overflow-x-auto">
              <table className="w-full min-w-[34rem] text-sm">
                <caption className="sr-only">Run summary, A versus B</caption>
                <thead>
                  <tr className="border-b border-border text-left text-[11px] text-muted-foreground">
                    <th scope="col" className="py-2 pr-3 font-medium" />
                    <th scope="col" className="py-2 pr-3 font-medium">A</th>
                    <th scope="col" className="py-2 pr-3 font-medium">B</th>
                    <th scope="col" className="py-2 text-right font-medium">Δ (B − A)</th>
                  </tr>
                </thead>
                <tbody className="[&_td]:py-1.5 [&_td]:pr-3 [&_th]:py-1.5 [&_th]:pr-3 [&_th]:text-left [&_th]:font-normal [&_th]:text-muted-foreground">
                  <tr className="border-b border-border/60">
                    <th scope="row">Run</th>
                    <td><Link className="font-mono text-[12px] underline underline-offset-2" to={`/runs/${data.a.id}`}>{data.a.id}</Link></td>
                    <td><Link className="font-mono text-[12px] underline underline-offset-2" to={`/runs/${data.b.id}`}>{data.b.id}</Link></td>
                    <td />
                  </tr>
                  <tr className="border-b border-border/60">
                    <th scope="row">Scenario</th>
                    <td className="break-all font-mono text-[12px]">{ra.scenario_id ?? "–"}</td>
                    <td className="break-all font-mono text-[12px]">{rb.scenario_id ?? "–"}</td>
                    <td className="text-right text-[12px] text-muted-foreground">{ra.scenario_id === rb.scenario_id ? "same" : "different"}</td>
                  </tr>
                  <tr className="border-b border-border/60">
                    <th scope="row">Verdict</th>
                    <td><VerdictLabel verdict={ra.verdict} /></td>
                    <td><VerdictLabel verdict={rb.verdict} /></td>
                    <td className="text-right text-[12px]">{ra.verdict === rb.verdict ? "unchanged" : "changed"}</td>
                  </tr>
                  {(
                    [
                      ["Risk Index", ra.risk_index.toFixed(3), rb.risk_index.toFixed(3), signed(rb.risk_index - ra.risk_index)],
                      ["Privacy score", ra.privacy_score, rb.privacy_score, signed(rb.privacy_score - ra.privacy_score, 0)],
                      ["WSL / ρ_S", `${ra.wsl} / ${ra.rho_s}`, `${rb.wsl} / ${rb.rho_s}`, signed(rb.wsl - ra.wsl, 0)],
                      ["Leaked / vault secrets", `${ra.summary.leaked_secrets} / ${ra.summary.vault_secrets}`, `${rb.summary.leaked_secrets} / ${rb.summary.vault_secrets}`, signed(rb.summary.leaked_secrets - ra.summary.leaked_secrets, 0)],
                      ["Findings", ra.findings.length, rb.findings.length, signed(rb.findings.length - ra.findings.length, 0)],
                      ["Gate", ra.blocked ? "blocked" : "passed", rb.blocked ? "blocked" : "passed", ra.blocked === rb.blocked ? "unchanged" : rb.blocked ? "now blocked" : "now passes"],
                    ] as [string, string | number, string | number, string][]
                  ).map(([label, va, vb, d]) => (
                    <tr key={label} className="border-b border-border/60">
                      <th scope="row">{label}</th>
                      <td className="font-mono tnum">{va}</td>
                      <td className="font-mono tnum">{vb}</td>
                      <td className="text-right font-mono tnum">{d}</td>
                    </tr>
                  ))}
                  <tr className="border-b border-border/60">
                    <th scope="row">Leaked by level</th>
                    <td className="font-mono text-[12px] tnum">{LEVELS.map((l) => `${l}:${ra.summary.level_profile[l] ?? 0}`).join(" ")}</td>
                    <td className="font-mono text-[12px] tnum">{LEVELS.map((l) => `${l}:${rb.summary.level_profile[l] ?? 0}`).join(" ")}</td>
                    <td />
                  </tr>
                  <tr>
                    <th scope="row">Detection</th>
                    <td><DetectionBadge detection={ra.detection} /></td>
                    <td><DetectionBadge detection={rb.detection} /></td>
                    <td />
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          {/* per channel */}
          <section aria-labelledby="cmp-channels">
            <h2 id="cmp-channels" className="mb-2 text-sm font-medium">Per emission channel</h2>
            <div className="overflow-x-auto rounded-lg border border-border bg-card">
              <table className="w-full min-w-[30rem] text-sm">
                <caption className="sr-only">Channel Risk Index, A versus B</caption>
                <thead>
                  <tr className="border-b border-border text-left text-[11px] text-muted-foreground">
                    <th scope="col" className="px-4 py-2 font-medium">Channel</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">RI A</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">RI B</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Δ</th>
                    <th scope="col" className="px-4 py-2 text-right font-medium">Findings A → B</th>
                  </tr>
                </thead>
                <tbody>
                  {channels.map((c) => {
                    const d = c.riB - c.riA
                    return (
                      <tr key={c.channel} className="border-b border-border/60 last:border-b-0">
                        <td className="px-4 py-1.5 font-mono text-[13px]">{c.channel}</td>
                        <td className="px-3 py-1.5 text-right font-mono tnum">{c.riA.toFixed(3)}</td>
                        <td className="px-3 py-1.5 text-right font-mono tnum">{c.riB.toFixed(3)}</td>
                        <td className={cn("px-3 py-1.5 text-right font-mono tnum", d > 0.0005 && "text-sev-l4", d < -0.0005 && "text-sev-ok")}>
                          {signed(d)}
                          <span className="sr-only">{d > 0.0005 ? " (worse)" : d < -0.0005 ? " (better)" : ""}</span>
                        </td>
                        <td className="px-4 py-1.5 text-right font-mono tnum">
                          {c.fA} → {c.fB}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </section>

          {/* findings */}
          <section aria-labelledby="cmp-findings">
            <h2 id="cmp-findings" className="mb-1 text-sm font-medium">Findings</h2>
            <p className="mb-2 text-[12px] text-muted-foreground">
              Matched on channel, data type, level and masked value; finding ids are per run and cannot be matched.
            </p>
            <div className="rounded-lg border border-border bg-card">
              <DataTable
                caption="Findings added, resolved and unchanged between A and B"
                columns={diffColumns}
                rows={statusFilter === "all" ? diff : diff.filter((d) => d.status === statusFilter)}
                rowKey={(d) => d.key}
                initialSort={{ id: "status", dir: "asc" }}
                exportName={`compare-${data.a.id}-${data.b.id}`}
                empty="Neither run has a finding."
                toolbar={
                  <div className="flex flex-wrap gap-1" role="group" aria-label="Filter by change">
                    {(["all", "resolved", "added", "unchanged"] as const).map((s) => (
                      <button
                        key={s}
                        type="button"
                        aria-pressed={statusFilter === s}
                        onClick={() => setStatusFilter(s)}
                        className={cn(
                          "rounded border px-2 py-0.5 text-[12px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                          statusFilter === s ? "border-foreground bg-foreground text-background" : "border-border text-muted-foreground hover:text-foreground",
                        )}
                      >
                        {s} <span className="font-mono tnum">{s === "all" ? diff.length : counts[s]}</span>
                      </button>
                    ))}
                  </div>
                }
              />
            </div>
          </section>
        </div>
      )}
    </div>
  )
}
