// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import type { Finding } from "./api"

export type Status = "resolved" | "added" | "unchanged"
export interface DiffRow {
  key: string
  status: Status
  finding: Finding
}

/**
 * Reports carry no stable finding fingerprint (finding ids are per run), so a
 * finding is matched on what identifies the disclosure: channel, data type,
 * level and masked value.
 */
export function fingerprint(f: Finding) {
  return `${f.channel}|${f.data_type}|${f.level}|${f.redacted_value}`
}

export function diffFindings(a: Finding[], b: Finding[]): DiffRow[] {
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

