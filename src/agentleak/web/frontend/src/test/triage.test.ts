// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
//
// Pure-logic tests for triage wording and the server-side run filter.
import { describe, expect, it } from "vitest"
import type { TriageItem, TriageView } from "@/lib/api"
import { runQueryString } from "@/lib/api"
import {
  expiryBounds,
  provenanceText,
  requiresRationale,
  triageBreakdown,
  triageText,
  triagedSentence,
  validateDecision,
} from "@/lib/triage"
import { dayStart, queryFromParams } from "@/features/RunsBrowser"

function item(over: Partial<TriageItem>): TriageItem {
  return {
    finding_id: "f1",
    identity: "fingerprint",
    state: "untriaged",
    effective_state: "untriaged",
    expired: false,
    carried: false,
    carried_from: null,
    decision: null,
    ...over,
  }
}

function view(fp: number, changed: boolean): TriageView {
  return {
    run_id: "r",
    project_id: "p",
    identity: { method: "fingerprint", detail: "", key: "key file" },
    findings: [],
    summary: { total: 6, triaged: fp, untriaged: 6 - fp, true_positive: 0, false_positive: fp, accepted_risk: 0, needs_review: 0, expired: 0, carried: 1 },
    score: {
      measured: { risk_index: 0.44, privacy_score: 56, wsl: 11, rho_s: 25, leaked_secrets: 4, verdict: "High risk", blocked: true },
      triaged: {
        label: "excluding findings triaged as false positive",
        risk_index: changed ? 0.28 : 0.44,
        privacy_score: changed ? 72 : 56,
        wsl: changed ? 7 : 11,
        rho_s: 25,
        leaked_secrets: changed ? 3 : 4,
        false_positive_findings: fp,
        total_findings: 6,
        excluded_secrets: changed ? 1 : 0,
        exact: true,
        method: "fingerprint",
        changed,
      },
    },
    states: ["true_positive", "false_positive", "accepted_risk", "needs_review"],
  }
}

describe("triage wording", () => {
  it("states the decision in force, with expiry", () => {
    expect(triageText(undefined)).toBe("Untriaged")
    const ar = item({
      state: "accepted_risk",
      effective_state: "accepted_risk",
      decision: { id: "d", run_id: "r", finding_id: "f1", state: "accepted_risk", rationale: "x", expires_at: 1, expires_on: "2027-01-31", reviewer_email: "a@example.test", created_at: 1 },
    })
    expect(triageText(ar)).toBe("Accepted risk until 2027-01-31")
    expect(triageText({ ...ar, effective_state: "needs_review", expired: true })).toBe(
      "Needs review: accepted risk expired 2027-01-31",
    )
  })

  it("says where a carried decision came from", () => {
    const carried = item({ state: "false_positive", effective_state: "false_positive", carried: true, carried_from: { run_id: "run_a", finding_id: "f9", run_exists: false, same_run: false } })
    expect(provenanceText(carried)).toBe("carried over from run run_a (since deleted)")
    expect(provenanceText({ ...carried, carried_from: { run_id: "r", finding_id: "f9", run_exists: true, same_run: true } })).toBe(
      "same value as f9 in this run",
    )
    expect(provenanceText(item({}))).toBeNull()
  })

  it("gives both denominators and never a verdict", () => {
    const s = triagedSentence(view(2, true))
    expect(s).toContain("2 of 6 findings triaged as false positive")
    expect(s).toContain("1 of 4 leaked secrets")
    expect(s).toContain("WSL 7 / ρ_S 25")
    expect(s).not.toMatch(/Pass|Fail|safe/i)
    expect(triagedSentence(view(1, false))).toContain("unchanged")
    expect(triageBreakdown(view(2, true))).toBe("Triage: 2 false positive, 4 untriaged (6 findings; 1 carried over).")
  })
})

describe("triage validation mirrors the server", () => {
  const now = new Date("2026-11-15T12:00:00Z")
  it("requires a rationale except for a true positive", () => {
    expect(requiresRationale("true_positive")).toBe(false)
    expect(validateDecision("true_positive", "", "", now)).toBeNull()
    expect(validateDecision("false_positive", " ", "", now)).toMatch(/rationale/)
    expect(validateDecision("false_positive", "x".repeat(1001), "", now)).toMatch(/1000/)
  })
  it("bounds the expiry date", () => {
    expect(expiryBounds(now)).toEqual({ min: "2026-11-16", max: "2029-11-17" })
    expect(validateDecision("accepted_risk", "known", "2026-11-15", now)).toMatch(/after today/)
    expect(validateDecision("accepted_risk", "known", "2026-11-16", now)).toBeNull()
    expect(validateDecision("accepted_risk", "known", "2030-01-01", now)).toMatch(/three years/)
    expect(validateDecision("needs_review", "check", "2026-12-01", now)).toMatch(/accepted risk only/)
  })
})

describe("run filter", () => {
  it("maps the URL to the API query, with an inclusive end day", () => {
    const q = queryFromParams(new URLSearchParams("verdict=Fail&from=2026-11-01&to=2026-11-02&sort=risk_index&dir=asc&page=2&q=%20abc%20"))
    expect(q.verdict).toBe("Fail")
    expect(q.since).toBe(dayStart("2026-11-01"))
    expect(q.until).toBe(dayStart("2026-11-02")! + 86_400)
    expect(q).toMatchObject({ sort: "risk_index", dir: "asc", limit: 50, offset: 100, q: "abc" })
    expect(queryFromParams(new URLSearchParams("sort=bogus")).sort).toBe("created_at")
    expect(dayStart("2026-13-45x")).toBeUndefined()
  })
  it("drops empty parameters", () => {
    expect(runQueryString({ q: "", verdict: undefined, limit: 50, gate: "" })).toBe("?limit=50")
  })
})
