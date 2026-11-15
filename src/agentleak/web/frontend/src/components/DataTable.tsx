// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { Fragment, useEffect, useMemo, useState, type ReactNode } from "react"
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Download } from "lucide-react"
import { toast } from "sonner"
import { exportTable, type Cell } from "@/lib/export"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"

export interface Column<T> {
  id: string
  header: string
  /** Raw value: used for sorting and for CSV/JSON export. */
  value: (row: T) => Cell
  /** Rendered cell; defaults to the raw value. */
  cell?: (row: T) => ReactNode
  align?: "left" | "right"
  className?: string
  /** Hide on narrow screens (still exported). */
  hideBelow?: "sm" | "md" | "lg"
  sortable?: boolean
  exportable?: boolean
}

export type SortState = { id: string; dir: "asc" | "desc" } | null

const HIDE: Record<string, string> = { sm: "hidden sm:table-cell", md: "hidden md:table-cell", lg: "hidden lg:table-cell" }

function compare(a: Cell, b: Cell): number {
  if (a === b) return 0
  if (a === null || a === undefined || a === "") return 1
  if (b === null || b === undefined || b === "") return -1
  if (typeof a === "number" && typeof b === "number") return a - b
  if (typeof a === "boolean" && typeof b === "boolean") return Number(a) - Number(b)
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" })
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  initialSort = null,
  toolbar,
  exportName,
  empty,
  pageSize,
  onRowClick,
  activeKey,
  selection,
  expanded,
  dense = true,
  footer,
}: {
  columns: Column<T>[]
  rows: T[]
  rowKey: (row: T) => string
  caption: string
  initialSort?: SortState
  toolbar?: ReactNode
  /** File stem for "Export"; omit to hide export. */
  exportName?: string
  empty?: ReactNode
  pageSize?: number
  onRowClick?: (row: T) => void
  activeKey?: string | null
  selection?: { selected: string[]; onChange: (keys: string[]) => void; max?: number; label?: (row: T) => string }
  expanded?: (row: T) => ReactNode | null
  dense?: boolean
  footer?: ReactNode
}) {
  const [sort, setSort] = useState<SortState>(initialSort)
  const [page, setPage] = useState(0)

  const sorted = useMemo(() => {
    if (!sort) return rows
    const col = columns.find((c) => c.id === sort.id)
    if (!col) return rows
    const out = [...rows].sort((a, b) => compare(col.value(a), col.value(b)))
    return sort.dir === "desc" ? out.reverse() : out
  }, [rows, columns, sort])

  const pages = pageSize ? Math.max(1, Math.ceil(sorted.length / pageSize)) : 1
  useEffect(() => {
    if (page >= pages) setPage(0)
  }, [page, pages])

  // Keep the active row on screen when it is set from outside (permalink, jump).
  useEffect(() => {
    if (!pageSize || !activeKey) return
    const idx = sorted.findIndex((r) => rowKey(r) === activeKey)
    if (idx >= 0) setPage(Math.floor(idx / pageSize))
  }, [activeKey, pageSize, sorted, rowKey])

  const visible = pageSize ? sorted.slice(page * pageSize, page * pageSize + pageSize) : sorted

  function toggleSort(id: string) {
    setSort((s) => (s?.id !== id ? { id, dir: "desc" } : s.dir === "desc" ? { id, dir: "asc" } : null))
  }

  function doExport(format: "csv" | "json") {
    if (!exportName) return
    const cols = columns.filter((c) => c.exportable !== false)
    const file = exportTable(
      exportName,
      format,
      cols.map((c) => c.id),
      sorted.map((r) => cols.map((c) => c.value(r))),
    )
    toast.success(`Exported ${sorted.length} row${sorted.length === 1 ? "" : "s"} to ${file}`)
  }

  const sel = selection ? new Set(selection.selected) : null
  function toggleRow(key: string) {
    if (!selection || !sel) return
    if (sel.has(key)) selection.onChange(selection.selected.filter((k) => k !== key))
    else {
      const next = [...selection.selected, key]
      selection.onChange(selection.max ? next.slice(-selection.max) : next)
    }
  }

  const pad = dense ? "py-2" : "py-3"
  const colCount = columns.length + (selection ? 1 : 0)

  return (
    <div className="min-w-0">
      {(toolbar || exportName) && (
        <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">{toolbar}</div>
          <span className="text-[11px] tnum text-muted-foreground" aria-live="polite">
            {sorted.length === rows.length ? `${rows.length} rows` : `${sorted.length} of ${rows.length} rows`}
          </span>
          {exportName && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="sm" className="h-8" disabled={!sorted.length}>
                  <Download /> Export
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => doExport("csv")}>CSV, rows shown</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => doExport("json")}>JSON, rows shown</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr className="border-b border-border text-left text-[11px] text-muted-foreground">
              {selection && (
                <th scope="col" className="w-9 px-3 py-2 font-medium">
                  <span className="sr-only">Select</span>
                </th>
              )}
              {columns.map((c) => {
                const active = sort?.id === c.id
                const sortable = c.sortable !== false
                return (
                  <th
                    key={c.id}
                    scope="col"
                    aria-sort={active ? (sort!.dir === "asc" ? "ascending" : "descending") : undefined}
                    className={cn(
                      "whitespace-nowrap px-3 py-2 font-medium first:pl-4 last:pr-4",
                      c.align === "right" && "text-right",
                      c.hideBelow && HIDE[c.hideBelow],
                    )}
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(c.id)}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-sm hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                          active && "text-foreground",
                        )}
                      >
                        {c.header}
                        {active ? (
                          sort!.dir === "asc" ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />
                        ) : null}
                      </button>
                    ) : (
                      c.header
                    )}
                  </th>
                )
              })}
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 && (
              <tr>
                <td colSpan={colCount} className="px-4 py-10 text-center text-sm text-muted-foreground">
                  {empty ?? "No rows."}
                </td>
              </tr>
            )}
            {visible.map((row) => {
              const key = rowKey(row)
              const extra = expanded?.(row)
              const isActive = activeKey === key
              return (
                <Fragment key={key}>
                  <tr
                    id={`row-${key}`}
                    data-active={isActive || undefined}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    className={cn(
                      "border-b border-border/70 align-top transition-colors last:border-b-0",
                      onRowClick && "cursor-pointer hover:bg-muted/50",
                      isActive && "bg-muted/70",
                      sel?.has(key) && "bg-muted/40",
                    )}
                  >
                    {selection && (
                      <td className={cn("px-3", pad)} onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          className="size-3.5 accent-foreground"
                          checked={sel!.has(key)}
                          onChange={() => toggleRow(key)}
                          aria-label={`Select ${selection.label ? selection.label(row) : key}`}
                        />
                      </td>
                    )}
                    {columns.map((c) => (
                      <td
                        key={c.id}
                        className={cn(
                          "px-3 first:pl-4 last:pr-4",
                          pad,
                          c.align === "right" && "text-right tnum",
                          c.hideBelow && HIDE[c.hideBelow],
                          c.className,
                        )}
                      >
                        {c.cell ? c.cell(row) : String(c.value(row) ?? "")}
                      </td>
                    ))}
                  </tr>
                  {extra && (
                    <tr className="border-b border-border/70 bg-muted/30">
                      <td colSpan={colCount} className="px-4 py-3">
                        {extra}
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
      {(pageSize && pages > 1) || footer ? (
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
          <div>{footer}</div>
          {pageSize && pages > 1 && (
            <div className="flex items-center gap-2">
              <span className="tnum">
                {page * pageSize + 1}–{Math.min(sorted.length, (page + 1) * pageSize)} of {sorted.length}
              </span>
              <Button variant="ghost" size="icon" className="size-7" disabled={page === 0} onClick={() => setPage(page - 1)} aria-label="Previous page">
                <ChevronLeft />
              </Button>
              <Button variant="ghost" size="icon" className="size-7" disabled={page >= pages - 1} onClick={() => setPage(page + 1)} aria-label="Next page">
                <ChevronRight />
              </Button>
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}
