// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { Link } from "react-router-dom"
import { ScanSearch } from "lucide-react"
import { Button } from "@/components/ui/button"
import { RunsBrowser } from "@/features/RunsBrowser"
import { PageHeader } from "@/layout/AppShell"

export function Runs() {
  return (
    <div className="min-w-0">
      <PageHeader
        title="Runs"
        description="Every stored analysis in this workspace, filtered and paged on the server. Tick two runs to compare them. Export takes every run that matches the filter, not only this page."
        actions={
          <Button asChild>
            <Link to="/analyze">
              <ScanSearch /> Analyze a trace
            </Link>
          </Button>
        }
      />
      <div className="rounded-lg border border-border bg-card">
        <RunsBrowser
          empty={
            <>
              No runs yet. <Link className="underline underline-offset-2" to="/analyze">Analyze a trace</Link> and save it as a run.
            </>
          }
        />
      </div>
    </div>
  )
}
