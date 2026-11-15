// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { Link } from "react-router-dom"
import { ScanSearch } from "lucide-react"
import { Button } from "@/components/ui/button"
import { RunsTable, useAllRuns } from "@/features/RunsTable"
import { PageHeader } from "@/layout/AppShell"

export function Runs() {
  const { runs, error } = useAllRuns()
  return (
    <div className="min-w-0">
      <PageHeader
        title="Runs"
        description="Every stored analysis in this workspace. Tick two runs to compare them; export exports the rows shown."
        actions={
          <Button asChild>
            <Link to="/analyze">
              <ScanSearch /> Analyze a trace
            </Link>
          </Button>
        }
      />
      {error && <p role="alert" className="mb-3 text-sm text-sev-l4">Could not load runs: {error}</p>}
      <div className="rounded-lg border border-border bg-card">
        {runs === null && !error ? (
          <div className="space-y-2 p-4" aria-busy="true">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-7 rounded bg-muted motion-safe:animate-pulse" />
            ))}
          </div>
        ) : (
          <RunsTable
            runs={runs ?? []}
            exportName="runs"
            empty={
              <>
                No runs yet. <Link className="underline underline-offset-2" to="/analyze">Analyze a trace</Link> and save it as a run.
              </>
            }
          />
        )}
      </div>
    </div>
  )
}
