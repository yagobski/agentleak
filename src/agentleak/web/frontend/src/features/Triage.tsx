// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useCallback, useEffect, useId, useState } from "react"
import { Ban, CircleCheck, CircleDashed, CircleHelp, Hourglass, Loader2 } from "lucide-react"
import { toast } from "sonner"
import {
  api,
  type Finding,
  type TriageHistory,
  type TriageItem,
  type TriageStateOrNone,
  type TriageView,
} from "@/lib/api"
import {
  RATIONALE_MAX,
  TRIAGE_META,
  TRIAGE_STATES,
  expiryBounds,
  provenanceText,
  requiresRationale,
  triageBreakdown,
  triageText,
  triagedSentence,
  validateDecision,
} from "@/lib/triage"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { formatStamp } from "./RunsTable"

export interface DecisionInput {
  findingIds: string[]
  state: TriageStateOrNone
  rationale: string
  expiresOn: string
}

/** Triage of one stored run: the view in force and a way to record decisions. */
export function useTriage(runId: string | undefined) {
  const [view, setView] = useState<TriageView | null>(null)
  const [error, setError] = useState("")
  const load = useCallback(() => {
    if (!runId) return
    setError("")
    api
      .triage(runId)
      .then(setView)
      .catch((e) => setError((e as Error).message))
  }, [runId])
  useEffect(() => {
    setView(null)
    load()
  }, [load])

  const decide = useCallback(
    async (d: DecisionInput) => {
      if (!runId) return
      const next = await api.setTriage(runId, {
        finding_ids: d.findingIds,
        state: d.state,
        rationale: d.rationale.trim(),
        expires_on: d.state === "accepted_risk" && d.expiresOn ? d.expiresOn : null,
      })
      setView(next)
      const n = d.findingIds.length
      toast.success(`${TRIAGE_META[d.state].label}: ${n} finding${n === 1 ? "" : "s"}`)
    },
    [runId],
  )
  return { view, error, reload: load, decide }
}

const ICON: Record<TriageStateOrNone, typeof CircleCheck> = {
  true_positive: CircleCheck,
  false_positive: Ban,
  accepted_risk: Hourglass,
  needs_review: CircleHelp,
  untriaged: CircleDashed,
}

const TONE: Record<TriageStateOrNone, string> = {
  true_positive: "text-sev-l4",
  false_positive: "text-muted-foreground",
  accepted_risk: "text-sev-l2",
  needs_review: "text-sev-l3",
  untriaged: "text-muted-foreground",
}

/** The decision in force. Text and icon shape carry the state; color only reinforces it. */
export function TriageChip({ item, compact = false }: { item?: TriageItem; compact?: boolean }) {
  const state = item?.effective_state ?? "untriaged"
  const Icon = ICON[state]
  const from = provenanceText(item)
  return (
    <span className="inline-flex min-w-0 flex-col">
      <span className={cn("inline-flex items-center gap-1 whitespace-nowrap text-[12px]", TONE[state], state !== "untriaged" && "font-medium")}>
        <Icon className="size-3.5 shrink-0" aria-hidden />
        {compact ? TRIAGE_META[state].label : triageText(item)}
      </span>
      {from && !compact && <span className="truncate text-[11px] text-muted-foreground">{from}</span>}
    </span>
  )
}

/** Record one decision for one or more findings. */
export function TriageDialog({
  open,
  onOpenChange,
  findingIds,
  initial,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  findingIds: string[]
  initial?: TriageItem
  onSubmit: (d: DecisionInput) => Promise<void>
}) {
  const uid = useId()
  const [state, setState] = useState<TriageStateOrNone>("true_positive")
  const [rationale, setRationale] = useState("")
  const [expiresOn, setExpiresOn] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open) return
    const current = initial?.effective_state
    setState(current && current !== "untriaged" ? current : "true_positive")
    setRationale(initial && !initial.carried ? initial.decision?.rationale ?? "" : "")
    setExpiresOn("")
    setError("")
  }, [open, initial])

  const bounds = expiryBounds()
  const n = findingIds.length
  const canClear = !!initial && initial.state !== "untriaged" && !initial.carried
  const options: TriageStateOrNone[] = canClear ? [...TRIAGE_STATES, "untriaged"] : TRIAGE_STATES

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const problem = validateDecision(state, rationale, state === "accepted_risk" ? expiresOn : "")
    if (problem) {
      setError(problem)
      return
    }
    setBusy(true)
    setError("")
    try {
      await onSubmit({ findingIds, state, rationale, expiresOn: state === "accepted_risk" ? expiresOn : "" })
      onOpenChange(false)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-28px)] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-lg">
            Triage {n === 1 ? `finding ${findingIds[0]}` : `${n} findings`}
          </DialogTitle>
          <DialogDescription>
            The measured score, verdict and gate do not change. A decision carries over to the same value on the same
            channel in later runs of this project.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4" noValidate>
          <fieldset>
            <legend className="mb-2 text-[13px] font-medium">Decision</legend>
            <div className="space-y-1.5">
              {options.map((s) => {
                const Icon = ICON[s]
                return (
                  <label
                    key={s}
                    className={cn(
                      "flex cursor-pointer gap-2.5 rounded-md border px-3 py-2 text-[13px] focus-within:ring-2 focus-within:ring-ring",
                      state === s ? "border-foreground" : "border-border hover:bg-muted/50",
                    )}
                  >
                    <input
                      type="radio"
                      name={`${uid}-state`}
                      value={s}
                      checked={state === s}
                      onChange={() => setState(s)}
                      className="mt-0.5 accent-foreground"
                    />
                    <span className="min-w-0">
                      <span className={cn("inline-flex items-center gap-1 font-medium", TONE[s])}>
                        <Icon className="size-3.5" aria-hidden />
                        {s === "untriaged" ? "Clear the decision" : TRIAGE_META[s].label}
                      </span>
                      <span className="block text-[12px] text-muted-foreground">{TRIAGE_META[s].help}</span>
                    </span>
                  </label>
                )
              })}
            </div>
          </fieldset>

          <div>
            <label htmlFor={`${uid}-why`} className="text-[13px] font-medium">
              Rationale{" "}
              <span className="font-normal text-muted-foreground">{requiresRationale(state) ? "(required)" : "(optional)"}</span>
            </label>
            <Textarea
              id={`${uid}-why`}
              value={rationale}
              maxLength={RATIONALE_MAX}
              onChange={(e) => setRationale(e.target.value)}
              aria-describedby={`${uid}-why-help`}
              aria-required={requiresRationale(state)}
              className="mt-1.5 min-h-[72px] text-[13px]"
              placeholder="Why, in a sentence. Do not paste the sensitive value."
            />
            <p id={`${uid}-why-help`} className="mt-1 flex justify-between gap-2 text-[11px] text-muted-foreground">
              <span>Stored as plain text with your account and the time.</span>
              <span className="tnum">
                {rationale.length} / {RATIONALE_MAX}
              </span>
            </p>
          </div>

          {state === "accepted_risk" && (
            <div>
              <label htmlFor={`${uid}-exp`} className="text-[13px] font-medium">
                Review again on <span className="font-normal text-muted-foreground">(optional, UTC)</span>
              </label>
              <input
                id={`${uid}-exp`}
                type="date"
                value={expiresOn}
                min={bounds.min}
                max={bounds.max}
                onChange={(e) => setExpiresOn(e.target.value)}
                aria-describedby={`${uid}-exp-help`}
                className="mt-1.5 block h-9 rounded-md border border-input bg-background px-2 text-[13px]"
              />
              <p id={`${uid}-exp-help`} className="mt-1 text-[11px] text-muted-foreground">
                From that day the finding reads "needs review" again and says why. Empty means no expiry.
              </p>
            </div>
          )}

          {error && (
            <p role="alert" className="text-[13px] text-sev-l4">
              {error}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {busy && <Loader2 className="animate-spin motion-reduce:animate-none" />}
              Save decision
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/** Decision in force and the audit trail of one finding (expanded findings row). */
export function TriageDetail({
  runId,
  finding,
  item,
  onEdit,
}: {
  runId: string
  finding: Finding
  item?: TriageItem
  onEdit: () => void
}) {
  const [history, setHistory] = useState<TriageHistory | null>(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState("")
  const d = item?.decision
  // Reload the trail when the decision in force changes.
  const stamp = d?.id ?? "none"
  useEffect(() => {
    setHistory(null)
  }, [stamp])
  useEffect(() => {
    if (!open || history) return
    api
      .triageHistory(runId, finding.finding_id)
      .then(setHistory)
      .catch((e) => setError((e as Error).message))
  }, [open, history, runId, finding.finding_id])

  return (
    <div className="space-y-2 border-t border-border pt-2 text-[13px]">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-muted-foreground">Triage</span>
            <TriageChip item={item} />
          </div>
          {d && d.state !== "untriaged" && (
            <p className="break-words text-muted-foreground">
              {d.rationale ? <span className="text-foreground">“{d.rationale}”</span> : "No rationale."}{" "}
              {d.reviewer_email}, {formatStamp(d.created_at)}
            </p>
          )}
          {item?.expiry_note && <p className="text-sev-l3">{item.expiry_note}</p>}
        </div>
        <Button size="sm" variant="outline" className="h-7" onClick={onEdit}>
          {item && item.effective_state !== "untriaged" ? "Change" : "Triage"}
        </Button>
      </div>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="rounded-sm text-[12px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {open ? "Hide" : "Show"} audit trail
      </button>
      {open &&
        (error ? (
          <p role="alert" className="text-sev-l4">
            {error}
          </p>
        ) : !history ? (
          <p className="text-muted-foreground">Loading…</p>
        ) : history.decisions.length === 0 ? (
          <p className="text-muted-foreground">No decision has been recorded for this value on this channel.</p>
        ) : (
          <ol className="space-y-1.5 border-l border-border pl-3">
            {history.decisions.map((h) => (
              <li key={h.id} className="text-[12px]">
                <span className="font-medium">{h.state === "untriaged" ? "Cleared" : TRIAGE_META[h.state].label}</span>
                {h.expires_on && <span> until {h.expires_on}</span>}
                {h.in_force && <span className="ml-1 rounded border border-border px-1 text-[10px]">in force</span>}
                <span className="text-muted-foreground">
                  {" "}
                  · {h.reviewer_email} · {formatStamp(h.created_at)} · run{" "}
                  <span className="font-mono">{h.run_id}</span>
                  {h.run_id !== runId && !h.run_exists ? " (deleted)" : ""}
                </span>
                {h.rationale && <span className="block break-words text-muted-foreground">“{h.rationale}”</span>}
              </li>
            ))}
          </ol>
        ))}
    </div>
  )
}

/** The triaged figure, next to the measured one and clearly labelled as a second view. */
export function TriagedScore({ view }: { view: TriageView }) {
  const t = view.score.triaged
  return (
    <section aria-label="Triaged view of the score" className="mt-4 rounded-md border border-dashed border-border p-3 text-[13px]">
      <h3 className="text-[11px] font-medium text-muted-foreground">Triaged view, not the measured result</h3>
      <p className="mt-1">{triageBreakdown(view)}</p>
      {t.false_positive_findings > 0 && <p className="mt-1">{triagedSentence(view)}</p>}
      {t.changed && (
        <dl className="mt-2 grid grid-cols-3 gap-x-4 font-mono text-[12px] tnum">
          <div>
            <dt className="font-sans text-[11px] text-muted-foreground">RI excl. FP</dt>
            <dd>{t.risk_index.toFixed(3)}</dd>
          </div>
          <div>
            <dt className="font-sans text-[11px] text-muted-foreground">WSL / ρ_S</dt>
            <dd>
              {t.wsl} / {t.rho_s}
            </dd>
          </div>
          <div>
            <dt className="font-sans text-[11px] text-muted-foreground">Score excl. FP</dt>
            <dd>{t.privacy_score} / 100</dd>
          </div>
        </dl>
      )}
      <p className="mt-2 text-[11px] text-muted-foreground">
        The measured RI {view.score.measured.risk_index.toFixed(3)}, verdict and gate above are unchanged; accepted risks
        still count. ρ_S is kept: a false positive leaves the leaked set, not the vault.
        {!t.exact && t.changed && " Approximate: this run was stored without fingerprints, so secrets are grouped by masked value."}
      </p>
    </section>
  )
}
