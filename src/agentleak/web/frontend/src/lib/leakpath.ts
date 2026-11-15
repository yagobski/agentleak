// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
//
// Leak-path export (JSON and a self-contained SVG). Built from the report's
// leak_paths, whose values are already masked; nothing raw is added here.
import type { LeakPath, LeakStep, Report } from "./api"

export function uniqueSteps(steps: LeakStep[]): LeakStep[] {
  const seen = new Set<string>()
  return steps.filter((s) => {
    const k = `${s.event_id}|${s.kind}`
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })
}

export function leakPathsJson(report: Report): string {
  const paths = (report.leak_paths ?? []).map((p: LeakPath) => ({
    data_type: p.data_type,
    level: p.level_label,
    value_masked: p.value,
    entered_via: p.entered_via,
    channels: p.channels,
    agents: p.agents,
    steps: uniqueSteps(p.steps).map((s) => ({
      kind: s.kind,
      event_id: s.event_id,
      channel: s.channel,
      source: s.source,
      target: s.target,
      level: s.level_label,
    })),
  }))
  return JSON.stringify(
    {
      report: "agentleak-leak-paths",
      run_id: report.run_id,
      agent_name: report.agent_name,
      scenario_id: report.scenario_id ?? null,
      detection: report.detection ?? null,
      note: "Values are masked as in the report. Steps run from where a value entered (source) to where it was disclosed (leak).",
      paths,
    },
    null,
    2,
  )
}

function esc(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&apos;")
}

function clip(text: string, n: number): string {
  return text.length > n ? `${text.slice(0, n - 1)}…` : text
}

/**
 * One row per secret: a label, then a box per step joined by arrows. Fixed
 * colors (it is a file, read outside the app's theme); the step kind is in
 * the text, so color is never the only carrier.
 */
export function leakPathsSvg(report: Report): string {
  const paths = report.leak_paths ?? []
  const boxW = 210
  const boxH = 44
  const gap = 28
  const labelW = 230
  const rowH = 64
  const top = 56
  const maxSteps = Math.max(1, ...paths.map((p) => uniqueSteps(p.steps).length))
  const width = labelW + maxSteps * (boxW + gap) + 20
  const height = top + Math.max(1, paths.length) * rowH + 30
  const out: string[] = []
  out.push(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" font-family="ui-monospace, Menlo, monospace" font-size="12">`,
    `<title>${esc(`Leak paths, run ${report.run_id}`)}</title>`,
    `<rect width="100%" height="100%" fill="#ffffff"/>`,
    `<text x="16" y="24" font-family="system-ui, sans-serif" font-size="14" fill="#111111">${esc(`Leak paths: ${report.agent_name || "agent"} (run ${report.run_id})`)}</text>`,
    `<text x="16" y="42" font-family="system-ui, sans-serif" font-size="11" fill="#555555">${esc(`${paths.length} secret(s) disclosed; values masked; tiers: ${report.detection?.tiers.join(", ") || "not recorded"}`)}</text>`,
  )
  if (!paths.length) {
    out.push(`<text x="16" y="${top + 20}" fill="#555555">No leak path: no finding from the enabled deterministic detectors.</text>`)
  }
  paths.forEach((p, row) => {
    const y = top + row * rowH
    out.push(
      `<text x="16" y="${y + 20}" fill="#111111">${esc(clip(`${p.level_label} ${p.data_type}`, 30))}</text>`,
      `<text x="16" y="${y + 36}" fill="#555555">${esc(clip(p.value, 30))}</text>`,
    )
    uniqueSteps(p.steps).forEach((s, i) => {
      const x = labelW + i * (boxW + gap)
      const source = s.kind === "source"
      if (i > 0) {
        const ax = x - gap
        out.push(
          `<line x1="${ax + 2}" y1="${y + boxH / 2}" x2="${x - 6}" y2="${y + boxH / 2}" stroke="#555555" stroke-width="1.2"/>`,
          `<path d="M${x - 6},${y + boxH / 2 - 4} L${x},${y + boxH / 2} L${x - 6},${y + boxH / 2 + 4} z" fill="#555555"/>`,
        )
      }
      out.push(
        `<rect x="${x}" y="${y}" width="${boxW}" height="${boxH}" rx="4" fill="${source ? "#ffffff" : "#fbeaea"}" stroke="${source ? "#777777" : "#a32020"}"${source ? ' stroke-dasharray="4 3"' : ""}/>`,
        `<text x="${x + 8}" y="${y + 17}" fill="#111111">${esc(clip(`${source ? "entered" : "leaked"} ${s.channel}`, 26))}</text>`,
        `<text x="${x + 8}" y="${y + 33}" fill="#555555">${esc(clip(`${s.event_id} ${s.source}→${s.target}`, 26))}</text>`,
      )
    })
  })
  out.push("</svg>")
  return out.join("\n")
}
