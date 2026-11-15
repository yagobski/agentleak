// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { download } from "./format"

export type Cell = string | number | boolean | null | undefined

function csvCell(value: Cell): string {
  if (value === null || value === undefined) return ""
  const text = String(value)
  // Quote when needed; neutralise spreadsheet formula injection on text cells.
  const safe = /^[=+\-@\t\r]/.test(text) && typeof value === "string" ? `'${text}` : text
  return /[",\n\r]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe
}

export function toCsv(headers: string[], rows: Cell[][]): string {
  return [headers, ...rows].map((r) => r.map(csvCell).join(",")).join("\r\n") + "\r\n"
}

export function toRecords(headers: string[], rows: Cell[][]): Record<string, Cell>[] {
  return rows.map((r) => Object.fromEntries(headers.map((h, i) => [h, r[i] ?? null])))
}

export function exportTable(name: string, format: "csv" | "json", headers: string[], rows: Cell[][]) {
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")
  const file = `${name}-${stamp}.${format}`
  if (format === "csv") download(file, toCsv(headers, rows), "text/csv;charset=utf-8")
  else download(file, JSON.stringify(toRecords(headers, rows), null, 2), "application/json")
  return file
}
