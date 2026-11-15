// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
//
// Pure-logic tests for the result views. Fixtures are the bundled synthetic
// healthcare_patient_summary scenario: its report (values masked) and trace.
import { describe, expect, it } from "vitest"
import type { Report, TraceDoc } from "@/lib/api"
import { diffFindings, fingerprint } from "@/lib/compare"
import { toCsv, toRecords } from "@/lib/export"
import { channelSplit } from "@/lib/meta"
import { channelEventCounts, channelRows, headline } from "@/features/ResultSummary"
import { reconstructEvents, traceMatchesReport } from "@/features/TraceExplorer"
import reportJson from "./fixtures/healthcare-report.json"
import traceJson from "./fixtures/healthcare-trace.json"

const report = reportJson as unknown as Report
const trace = traceJson as unknown as TraceDoc
const split = channelSplit(null)

describe("export", () => {
  it("quotes CSV cells and neutralises spreadsheet formulas", () => {
    const csv = toCsv(["a", "b"], [["x,y", '=HYPERLINK("e")'], [1.5, null]])
    expect(csv).toBe('a,b\r\n"x,y","\'=HYPERLINK(""e"")"\r\n1.5,\r\n')
  })
  it("maps rows to records with the visible headers", () => {
    expect(toRecords(["id", "ri"], [["r1", 0.44]])).toEqual([{ id: "r1", ri: 0.44 }])
  })
})

describe("channel split", () => {
  it("falls back to the AgentRisk baseline channels", () => {
    expect(split.sources).toEqual(["user_input", "tool_response"])
    expect(split.emissions).toContain("final_output")
    expect(split.emissions).not.toContain("tool_response")
  })
})

describe("verdict per channel", () => {
  it("counts events per channel from the report flow and from the trace identically", () => {
    expect(channelEventCounts(report)).toEqual(channelEventCounts(report, trace))
  })
  it("lists final_output first and marks channels absent from the trace", () => {
    const rows = channelRows(report, split)
    expect(rows[0].channel).toBe("final_output")
    expect(rows[0].findings).toBe(0)
    expect(rows.find((r) => r.channel === "generated_file")?.events).toBe(0)
    expect(rows.find((r) => r.channel === "shared_memory")?.maxLevel).toBe(4)
  })
  it("states the clean-answer / leaking-internals contrast with its denominator", () => {
    const h = headline(report, channelRows(report, split))
    expect(h.tone).toBe("contrast")
    expect(h.text).toContain("4 of 4 internal channels")
  })
  it("never calls a result without findings safe", () => {
    const clean = { ...report, findings: [], channel_risks: [] } as Report
    const h = headline(clean, channelRows(clean, split))
    expect(h.tone).toBe("clean")
    expect(h.text.toLowerCase()).not.toContain("safe")
    expect(h.text).toContain("No finding from the enabled deterministic detectors")
  })
})

describe("trace explorer", () => {
  it("rebuilds the finding-bearing events when the trace is not stored", () => {
    const events = reconstructEvents(report)
    const ids = events.map((e) => e.event_id)
    for (const f of report.findings) expect(ids).toContain(f.event_id)
    expect(ids).toEqual([...ids].sort())
    expect(events.length).toBeLessThanOrEqual(report.event_count)
  })
  it("accepts the original trace and rejects a different one", () => {
    expect(traceMatchesReport(trace, report)).toBeNull()
    const shorter = { ...trace, events: trace.events.slice(1) }
    expect(traceMatchesReport(shorter, report)).toMatch(/events/)
  })
})

describe("run comparison", () => {
  it("matches identical findings as unchanged", () => {
    const d = diffFindings(report.findings, report.findings)
    expect(d.every((r) => r.status === "unchanged")).toBe(true)
    expect(d).toHaveLength(report.findings.length)
  })
  it("reports every finding as resolved against a clean run, and as added the other way round", () => {
    expect(diffFindings(report.findings, []).every((r) => r.status === "resolved")).toBe(true)
    expect(diffFindings([], report.findings).every((r) => r.status === "added")).toBe(true)
  })
  it("keeps repeated disclosures apart by count", () => {
    const f = report.findings[0]
    const d = diffFindings([f, f], [f])
    expect(d.filter((r) => r.status === "unchanged")).toHaveLength(1)
    expect(d.filter((r) => r.status === "resolved")).toHaveLength(1)
    expect(fingerprint(f)).toContain(f.redacted_value)
  })
})
