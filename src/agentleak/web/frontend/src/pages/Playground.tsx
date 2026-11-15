// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useEffect, useState } from "react"
import { Link, Navigate, useSearchParams } from "react-router-dom"
import { ArrowRight } from "lucide-react"
import { toast } from "sonner"
import { api, type Project } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { RedTeamView } from "@/features/RedTeamView"
import { PageHeader } from "@/layout/AppShell"


function TargetReadiness({ project }: { project: Project }) {
  const agent = project.config.agent
  const agents = project.config.agents ?? []
  const hasPurpose = Boolean(project.description?.trim())
  const hasTarget = Boolean(agent?.model || agents.some((item) => item.endpoint?.model))
  const toolCount = agents.reduce((count, item) => count + (item.tools?.length ?? 0), 0)
  return (
    <Card className="mb-5 overflow-hidden">
      <div className="grid gap-4 p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
        <div className="min-w-0"><p className="text-sm font-semibold">Test configuration · {project.name}</p><p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{project.description || "Add the intended purpose and limits so campaign results can be interpreted against the right boundary."}</p></div>
        <div className="flex flex-wrap gap-2 text-[10px]"><span className={`rounded-full px-2 py-1 ${hasPurpose ? "bg-sev-ok/10 text-sev-ok" : "bg-sev-l2/10 text-sev-l2"}`}>{hasPurpose ? "purpose defined" : "purpose missing"}</span><span className={`rounded-full px-2 py-1 ${hasTarget ? "bg-sev-ok/10 text-sev-ok" : "bg-muted text-muted-foreground"}`}>{hasTarget ? "model endpoint ready" : "offline baseline only"}</span><span className="rounded-full bg-muted px-2 py-1 text-muted-foreground">{agents.length || 1} configured role(s)</span><span className="rounded-full bg-muted px-2 py-1 text-muted-foreground">{toolCount} declared tool(s)</span></div>
      </div>
    </Card>
  )
}

export function Playground() {
  const [params] = useSearchParams()
  const legacyScenario = params.get("scenario")
  const [projects, setProjects] = useState<Project[] | null>(null)
  const [selectedProjectId, setSelectedProjectId] = useState("")

  useEffect(() => {
    api
      .projects()
      .then((items) => {
        setProjects(items)
        if (items.length) setSelectedProjectId(items[0].id)
      })
      .catch((error) => {
        setProjects([])
        toast.error(`Could not load projects: ${(error as Error).message}`)
      })
  }, [])

  // Old links (/playground?scenario=…) analyzed a sample trace; that now lives on /analyze.
  if (legacyScenario) return <Navigate to={`/analyze?scenario=${encodeURIComponent(legacyScenario)}`} replace />

  const selectedProject = projects?.find((project) => project.id === selectedProjectId)

  return (
    <div className="min-w-0">
      <PageHeader
        title="Red team"
        description="Generate adversarial executions against a project's test harness, offline or with the model configured on the project. To score a trace you already have, use Analyze a trace."
      />
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3 rounded-lg border border-border bg-card p-4">
        <div className="min-w-[240px] flex-1">
          <label htmlFor="rt-project" className="text-[12px] text-muted-foreground">Project under test</label>
          {projects === null ? (
            <div className="mt-2 h-9 max-w-lg rounded-md bg-muted motion-safe:animate-pulse" />
          ) : projects.length ? (
            <select id="rt-project" value={selectedProjectId} onChange={(event) => setSelectedProjectId(event.target.value)} className="mt-1 h-9 w-full max-w-lg rounded-md border border-input bg-background px-2 text-sm">
              {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
            </select>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">A red-team campaign runs against a project. Create one first; it defines the model, tools and purpose the harness uses.</p>
          )}
        </div>
        <Button asChild variant="outline"><Link to={selectedProject ? `/projects/${selectedProject.id}?tab=settings` : "/projects"}>{selectedProject ? "Project settings" : "Create a project"}<ArrowRight className="size-3.5" /></Link></Button>
      </div>
      {selectedProject && <><TargetReadiness project={selectedProject} /><RedTeamView projectId={selectedProject.id} /></>}
    </div>
  )
}
