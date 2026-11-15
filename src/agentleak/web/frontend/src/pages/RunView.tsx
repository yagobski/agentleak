// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { GitCompareArrows, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { api, ApiError, type Project, type Run, type TraceDoc } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { ConfirmDialog } from "@/components/ConfirmDialog"
import { CopyLinkButton } from "@/features/Chips"
import { ResultSkeleton, ResultsView } from "@/features/ResultsView"
import { useCrumbs } from "@/layout/crumbs"

export function RunView() {
  const { id = "" } = useParams()
  const nav = useNavigate()
  const [run, setRun] = useState<Run | null>(null)
  const [project, setProject] = useState<Project | null>(null)
  const [error, setError] = useState<{ status?: number; message: string } | null>(null)
  const [trace, setTrace] = useState<TraceDoc | null>(null)
  const [confirm, setConfirm] = useState(false)

  useEffect(() => {
    setRun(null)
    setTrace(null)
    setError(null)
    api
      .run(id)
      .then((r) => {
        setRun(r)
        if (r.project_id) api.project(r.project_id).then(setProject).catch(() => {})
      })
      .catch((e) => setError({ status: e instanceof ApiError ? e.status : undefined, message: (e as Error).message }))
  }, [id])

  useCrumbs([
    { label: "Runs", to: "/runs" },
    ...(project ? [{ label: project.name, to: `/projects/${project.id}?tab=runs` }] : []),
    { label: id },
  ])

  async function remove() {
    if (!run) return
    try {
      await api.deleteRun(run.id)
      toast.success(`Deleted ${run.id}`)
      nav(run.project_id ? `/projects/${run.project_id}?tab=runs` : "/runs")
    } catch (e) {
      toast.error((e as Error).message)
    }
  }

  if (error) {
    return (
      <div className="max-w-xl rounded-lg border border-border p-5">
        <h1 className="text-base font-medium">{error.status === 404 ? "Run not found" : "Could not load this run"}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {error.status === 404
            ? `No run with id ${id} exists in this workspace. It may have been deleted.`
            : error.message}
        </p>
        <Button asChild variant="outline" size="sm" className="mt-3">
          <Link to="/runs">All runs</Link>
        </Button>
      </div>
    )
  }
  if (!run) return <ResultSkeleton />

  return (
    <div className="min-w-0">
      <div className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-border pb-3 text-[12px] text-muted-foreground">
        <span>
          Run <span className="font-mono text-foreground">{run.id}</span>
        </span>
        {project && (
          <span>
            in{" "}
            <Link className="text-foreground underline-offset-2 hover:underline" to={`/projects/${project.id}?tab=runs`}>
              {project.name}
            </Link>
          </span>
        )}
        <span>
          source <span className="font-mono text-foreground">{run.source}</span>
        </span>
        {run.label && (
          <span>
            label <span className="text-foreground">{run.label}</span>
          </span>
        )}
        <span>
          stored <time dateTime={new Date(run.created_at * 1000).toISOString()}>{new Date(run.created_at * 1000).toLocaleString()}</time>
        </span>
      </div>
      <ResultsView
        report={run.report}
        runId={run.id}
        trace={trace}
        onTrace={setTrace}
        actions={
          <>
            <CopyLinkButton path={`/runs/${run.id}`} />
            <Button variant="outline" size="sm" asChild>
              <Link to={`/compare?a=${run.id}`}>
                <GitCompareArrows /> Compare
              </Link>
            </Button>
            <Button variant="ghost" size="sm" className="text-sev-l4 hover:text-sev-l4" onClick={() => setConfirm(true)}>
              <Trash2 /> Delete
            </Button>
          </>
        }
      />
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={`Delete run ${run.id}?`}
        description="The stored report is removed from this workspace. This cannot be undone."
        confirmLabel="Delete run"
        onConfirm={remove}
      />
    </div>
  )
}
