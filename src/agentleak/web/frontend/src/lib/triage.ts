// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import type { TriageItem, TriageState, TriageStateOrNone, TriageView } from "./api"

export const TRIAGE_STATES: TriageState[] = ["true_positive", "false_positive", "accepted_risk", "needs_review"]

export const TRIAGE_META: Record<TriageStateOrNone, { label: string; help: string }> = {
  true_positive: { label: "True positive", help: "A real disclosure of sensitive data." },
  false_positive: {
    label: "False positive",
    help: "Not sensitive data, or not a disclosure. Excluded from the triaged score only.",
  },
  accepted_risk: {
    label: "Accepted risk",
    help: "A real disclosure the team accepts for now, optionally until a date. Still counted in every score.",
  },
  needs_review: { label: "Needs review", help: "Someone has to look at this finding again." },
  untriaged: { label: "Untriaged", help: "No decision recorded." },
}

export const RATIONALE_MAX = 1000
export const RATIONALE_MIN = 3
export const MAX_EXPIRY_DAYS = 3 * 366

export function requiresRationale(state: TriageStateOrNone): boolean {
  return state === "false_positive" || state === "accepted_risk" || state === "needs_review"
}

/** One line describing the decision in force, including expiry. */
export function triageText(item: TriageItem | undefined): string {
  if (!item || item.effective_state === "untriaged") return TRIAGE_META.untriaged.label
  if (item.expired) return `Needs review: accepted risk expired ${item.decision?.expires_on ?? ""}`.trim()
  const base = TRIAGE_META[item.effective_state].label
  if (item.effective_state === "accepted_risk" && item.decision?.expires_on) return `${base} until ${item.decision.expires_on}`
  return base
}

/** Where a decision came from, when it was not made on this finding. */
export function provenanceText(item: TriageItem | undefined): string | null {
  if (!item?.carried || !item.carried_from || item.state === "untriaged") return null
  const c = item.carried_from
  if (c.same_run) return `same value as ${c.finding_id} in this run`
  return `carried over from run ${c.run_id}${c.run_exists ? "" : " (since deleted)"}`
}

function utcToday(now: Date): Date {
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
}

export function isoDay(d: Date): string {
  return d.toISOString().slice(0, 10)
}

/** Bounds for the expiry date input (UTC days, as the server checks them). */
export function expiryBounds(now = new Date()): { min: string; max: string } {
  const today = utcToday(now)
  return {
    min: isoDay(new Date(today.getTime() + 86_400_000)),
    max: isoDay(new Date(today.getTime() + MAX_EXPIRY_DAYS * 86_400_000)),
  }
}

/** Client-side mirror of the server's checks, for an immediate message. */
export function validateDecision(
  state: TriageStateOrNone,
  rationale: string,
  expiresOn: string,
  now = new Date(),
): string | null {
  const text = rationale.trim()
  if (text.length > RATIONALE_MAX) return `The rationale is limited to ${RATIONALE_MAX} characters.`
  if (requiresRationale(state) && text.length < RATIONALE_MIN) return "Write a short rationale for this decision."
  if (expiresOn) {
    if (state !== "accepted_risk") return "An expiry date applies to an accepted risk only."
    if (!/^\d{4}-\d{2}-\d{2}$/.test(expiresOn)) return "Use a date, YYYY-MM-DD."
    const { min, max } = expiryBounds(now)
    if (expiresOn < min) return "The expiry date must be after today (UTC)."
    if (expiresOn > max) return "The expiry date is limited to three years ahead."
  }
  return null
}

/**
 * The triaged view as one sentence with both denominators. Never a verdict:
 * the measured result is what the gate and the verdict use.
 */
export function triagedSentence(view: TriageView): string {
  const t = view.score.triaged
  const head = `${t.false_positive_findings} of ${t.total_findings} finding${t.total_findings === 1 ? "" : "s"} triaged as false positive`
  if (!t.changed) {
    return t.false_positive_findings
      ? `${head}; every secret they cover is still disclosed by another finding, so the score excluding them is unchanged.`
      : `${head}.`
  }
  return `${head}, covering ${t.excluded_secrets} of ${view.score.measured.leaked_secrets} leaked secret${view.score.measured.leaked_secrets === 1 ? "" : "s"}. Score excluding them: RI ${t.risk_index.toFixed(3)} (WSL ${t.wsl} / ρ_S ${t.rho_s}), privacy score ${t.privacy_score} / 100.`
}

/** "Triage: 1 true positive, 2 false positive, 3 untriaged (6 findings; 2 carried over)." */
export function triageBreakdown(view: TriageView): string {
  const s = view.summary
  const parts = (["true_positive", "false_positive", "accepted_risk", "needs_review", "untriaged"] as const)
    .filter((k) => s[k] > 0)
    .map((k) => `${s[k]} ${TRIAGE_META[k].label.toLowerCase()}`)
  const extra = [s.carried ? `${s.carried} carried over` : "", s.expired ? `${s.expired} expired` : ""].filter(Boolean)
  return `Triage: ${parts.join(", ") || "none"} (${s.total} finding${s.total === 1 ? "" : "s"}${extra.length ? `; ${extra.join(", ")}` : ""}).`
}
