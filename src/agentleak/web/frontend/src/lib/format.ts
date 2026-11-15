// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import type { Badge, Report } from "./api"

// Severity badge -> CSS custom property name (used for SVG strokes / inline color).
const BADGE_VAR: Record<Badge, string> = {
  critical: "--sev-l4",
  high: "--sev-l3",
  medium: "--sev-l2",
  low: "--sev-l1",
}

export function badgeColor(badge: Badge): string {
  return `hsl(var(${BADGE_VAR[badge] ?? "--muted-foreground"}))`
}

// Tailwind classes for a severity chip.
export function badgeChipClass(badge: Badge): string {
  return {
    critical: "text-sev-l4 bg-sev-l4/12 ring-1 ring-inset ring-sev-l4/25",
    high: "text-sev-l3 bg-sev-l3/12 ring-1 ring-inset ring-sev-l3/25",
    medium: "text-sev-l2 bg-sev-l2/12 ring-1 ring-inset ring-sev-l2/25",
    low: "text-sev-l1 bg-sev-l1/12 ring-1 ring-inset ring-sev-l1/25",
  }[badge]
}

export function verdictVar(verdict: Report["verdict"]): string {
  return {
    Pass: "--sev-ok",
    "Conditional pass": "--sev-l2",
    "High risk": "--sev-l3",
    Fail: "--sev-l4",
  }[verdict]
}

export function verdictColor(verdict: Report["verdict"]): string {
  return `hsl(var(${verdictVar(verdict)}))`
}

// Privacy-score color band (0–100): mirrors the verdict thresholds.
export function scoreColor(score: number): string {
  if (score >= 90) return "hsl(var(--sev-ok))"
  if (score >= 70) return "hsl(var(--sev-l2))"
  if (score >= 40) return "hsl(var(--sev-l3))"
  return "hsl(var(--sev-l4))"
}

export const LEVEL_META: { label: string; badge: Badge; name: string }[] = [
  { label: "L4", badge: "critical", name: "special category / credential" },
  { label: "L3", badge: "high", name: "financial / legal / employment" },
  { label: "L2", badge: "medium", name: "behavioral / contact data" },
  { label: "L1", badge: "low", name: "public / organizational identifier" },
]

export function download(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
