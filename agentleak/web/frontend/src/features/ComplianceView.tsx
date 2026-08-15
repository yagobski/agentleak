// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useEffect, useMemo, useState } from "react"
import { AlertTriangle, CheckCircle2, ChevronRight, CircleDashed, ExternalLink, FileCheck2, Fingerprint, Info, Scale, ShieldCheck } from "lucide-react"
import type { Compliance, ControlResult, FrameworkResult } from "@/lib/api"
import { Card } from "@/components/ui/card"

function StatusIcon({ status }: { status: ControlResult["status"] }) {
  if (status === "at_risk") return <AlertTriangle className="size-4 shrink-0 text-sev-l4" />
  if (status === "info") return <Info className="size-4 shrink-0 text-primary" />
  if (status === "not_assessed") return <CircleDashed className="size-4 shrink-0 text-muted-foreground" />
  return <CheckCircle2 className="size-4 shrink-0 text-sev-ok" />
}

function FrameworkTab({ framework, active, onSelect }: { framework: FrameworkResult; active: boolean; onSelect: () => void }) {
  const clear = framework.status === "compliant"
  const defended = framework.controls.length - framework.at_risk - framework.not_assessed
  const pct = Math.round((defended / Math.max(1, framework.controls.length)) * 100)
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onSelect}
      className={`group w-full rounded-lg border p-3 text-left transition-all ${active ? "border-foreground/20 bg-card shadow-sm" : "border-transparent hover:bg-muted/50"}`}
    >
      <div className="flex items-start gap-2.5">
        <span className={`mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md ${clear ? "bg-sev-ok/10 text-sev-ok" : "bg-sev-l4/10 text-sev-l4"}`}>
          {clear ? <ShieldCheck className="size-3.5" /> : <AlertTriangle className="size-3.5" />}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-2">
            <span className="min-w-0 flex-1 text-xs font-semibold leading-snug">{framework.name}</span>
            <ChevronRight className={`mt-0.5 size-3 shrink-0 transition-transform ${active ? "translate-x-0.5 text-foreground" : "text-muted-foreground"}`} />
          </div>
          <div className="mt-2 flex items-center gap-2">
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full" style={{ width: `${pct}%`, background: clear ? "hsl(var(--sev-ok))" : "hsl(var(--sev-l4))" }} />
            </div>
            <span className="font-mono text-[10px] text-muted-foreground tnum">{pct}%</span>
          </div>
          <div className="mt-1.5 text-[10px] text-muted-foreground">{framework.at_risk ? `${framework.at_risk} control${framework.at_risk === 1 ? "" : "s"} at risk` : framework.not_assessed ? `${framework.not_assessed} governance gap${framework.not_assessed === 1 ? "" : "s"}` : `${framework.controls.length} controls clear`}</div>
        </div>
      </div>
    </button>
  )
}

function FrameworkDetail({ framework }: { framework: FrameworkResult }) {
  const clear = framework.status === "compliant"
  const controls = useMemo(
    () => [...framework.controls].sort((a, b) => Number(b.status === "at_risk") - Number(a.status === "at_risk")),
    [framework.controls],
  )
  const infoCount = framework.controls.filter((control) => control.status === "info").length
  const clearCount = framework.controls.filter((control) => control.status === "ok").length
  const notAssessedCount = framework.controls.filter((control) => control.status === "not_assessed").length

  return (
    <div role="tabpanel" className="min-w-0">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border p-5">
        <div>
          <div className="flex items-center gap-2">
            <Scale className="size-4 text-primary" />
            <h3 className="text-base font-semibold">{framework.name}</h3>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Control mapping for this run · evidence is derived from the captured trace.</p>
        </div>
        <a href={framework.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
          Official source <ExternalLink className="size-3" />
        </a>
      </div>

      <div className="grid gap-px border-b border-border bg-border sm:grid-cols-4">
        {[
          { label: "At risk", value: framework.at_risk, color: framework.at_risk ? "text-sev-l4" : "text-sev-ok" },
          { label: "Clear", value: clearCount, color: "text-sev-ok" },
          { label: "Context", value: infoCount, color: "text-primary" },
          { label: "Not assessed", value: notAssessedCount, color: "text-muted-foreground" },
        ].map((item) => (
          <div key={item.label} className="bg-card px-5 py-3">
            <div className={`font-mono text-xl font-semibold tnum ${item.color}`}>{item.value}</div>
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground">{item.label} controls</div>
          </div>
        ))}
      </div>

      <div className="p-4">
        {!clear && (
          <div className="mb-3 flex gap-3 rounded-lg border border-sev-l4/20 bg-sev-l4/[0.045] p-3">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-sev-l4" />
            <p className="text-xs leading-relaxed"><span className="font-semibold">Priority review required.</span> Resolve the flagged controls below before treating this run as release-ready.</p>
          </div>
        )}
        <div className="overflow-hidden rounded-lg border border-border">
          <ul className="divide-y divide-border">
            {controls.map((control) => (
              <li key={control.id} className={`flex gap-3 px-4 py-3.5 ${control.status === "at_risk" ? "bg-sev-l4/[0.025]" : ""}`}>
                <StatusIcon status={control.status} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[13px] font-semibold leading-tight">{control.name}</span>
                    <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">{control.id}</code>
                  </div>
                  <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">{control.rationale}</p>
                  {control.evidence.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {control.evidence.slice(0, 8).map((evidence, index) => (
                        <code key={`${evidence}-${index}`} className={`rounded px-1.5 py-0.5 text-[9px] ${control.status === "at_risk" ? "bg-sev-l4/10 text-sev-l4" : "bg-muted text-muted-foreground"}`}>
                          {evidence}
                        </code>
                      ))}
                    </div>
                  )}
                  {control.evidence_details?.finding_ids.length > 0 && (
                    <p className="mt-2 font-mono text-[9px] text-muted-foreground">Findings: {control.evidence_details.finding_ids.join(", ")}</p>
                  )}
                </div>
                <span className={`self-start shrink-0 rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${control.status === "at_risk" ? "bg-sev-l4/10 text-sev-l4" : control.status === "info" ? "bg-primary/10 text-primary" : control.status === "not_assessed" ? "bg-muted text-muted-foreground" : "bg-sev-ok/10 text-sev-ok"}`}>
                  {control.status === "at_risk" ? "At risk" : control.status === "info" ? "Context" : control.status === "not_assessed" ? "Not assessed" : "Clear"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}

export function ComplianceView({ compliance }: { compliance: Compliance }) {
  const frameworks = compliance?.frameworks ?? []
  const firstPriority = frameworks.find((framework) => framework.status === "non_compliant")?.id ?? frameworks[0]?.id ?? ""
  const [selectedId, setSelectedId] = useState(firstPriority)

  useEffect(() => {
    if (!frameworks.some((framework) => framework.id === selectedId)) setSelectedId(firstPriority)
  }, [firstPriority, frameworks, selectedId])

  if (!frameworks.length) return null
  const summary = compliance.summary
  const posture = compliance.posture
  const selected = frameworks.find((framework) => framework.id === selectedId) ?? frameworks[0]
  const clear = posture?.status === "compliant"

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold"><FileCheck2 className="size-4 text-primary" /> Compliance navigator</div>
          <p className="mt-1 text-xs text-muted-foreground">Select a law or framework to inspect its mapped controls and trace evidence.</p>
        </div>
        <span className="text-xs text-muted-foreground">{summary.compliant}/{summary.total} frameworks clear · {summary.controls_at_risk} at risk · {summary.controls_not_assessed} not assessed</span>
      </div>

      <div className={`flex gap-3 rounded-lg border px-4 py-3 ${clear ? "border-sev-ok/25 bg-sev-ok/[0.055]" : "border-sev-l4/25 bg-sev-l4/[0.045]"}`}>
        {clear ? <ShieldCheck className="mt-0.5 size-4 shrink-0 text-sev-ok" /> : <AlertTriangle className="mt-0.5 size-4 shrink-0 text-sev-l4" />}
        <div>
          <div className="text-sm font-semibold">{clear ? `Clear across all ${summary.total} frameworks` : `${summary.non_compliant} framework${summary.non_compliant === 1 ? "" : "s"} require action`}</div>
          <p className="mt-0.5 text-xs text-muted-foreground">{clear ? "No mapped control was triggered by this trace." : `Start with ${posture?.failed.map((item) => item.name).join(", ") || "the flagged framework"}; the highest-risk controls are listed first.`}</p>
        </div>
      </div>

      <Card className="overflow-hidden">
        <div className="grid lg:grid-cols-[285px_minmax(0,1fr)]">
          <div role="tablist" aria-orientation="vertical" className="border-b border-border bg-muted/20 p-3 lg:border-b-0 lg:border-r">
            <div className="mb-2 px-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Laws &amp; frameworks</div>
            <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-1">
              {frameworks.map((framework) => (
                <FrameworkTab key={framework.id} framework={framework} active={selected.id === framework.id} onSelect={() => setSelectedId(framework.id)} />
              ))}
            </div>
          </div>
          <FrameworkDetail framework={selected} />
        </div>
      </Card>
      <Card className="grid gap-4 p-4 sm:grid-cols-[auto_1fr_auto] sm:items-center">
        <span className="flex size-9 items-center justify-center rounded-md bg-primary/10 text-primary"><Fingerprint className="size-4" /></span>
        <div className="min-w-0">
          <div className="text-xs font-semibold">Compliance evidence manifest</div>
          <p className="mt-1 text-[11px] text-muted-foreground">{compliance.assurance.evidence_grade === "trace_and_policy" ? "Trace evidence plus deterministic privacy-policy assertions" : "Trace evidence only — add privacy assertions to assess governance controls"} · {compliance.evidence_matrix.length} linked finding{compliance.evidence_matrix.length === 1 ? "" : "s"}</p>
        </div>
        <code className="max-w-48 truncate rounded bg-muted px-2 py-1 font-mono text-[9px] text-muted-foreground" title={compliance.integrity.digest}>sha256:{compliance.integrity.digest.slice(0, 16)}…</code>
      </Card>
      <p className="text-[10px] leading-relaxed text-muted-foreground">This is an engineering control mapping, not legal certification. Confirm regulatory interpretation with qualified counsel.</p>
    </div>
  )
}
