import { ArrowRight, Bot, Database, HardDrive, Plug, Sparkles, User, Wrench } from "lucide-react"
import type { Badge as Sev } from "@/lib/api"
import { type LeakPath, type ModelEdge, type ModelNode, type ProjectModel } from "@/lib/api"
import { badgeChipClass, badgeColor } from "@/lib/format"
import { Card } from "@/components/ui/card"

const LEVEL_BADGE: Record<number, Sev> = { 4: "critical", 3: "high", 2: "medium", 1: "low" }

function levelColor(level: number): string {
  return level > 0 ? badgeColor(LEVEL_BADGE[level] ?? "low") : "hsl(var(--muted-foreground) / 0.45)"
}

const KIND_ICON: Record<string, typeof Bot> = {
  user: User,
  tool: Database,
  agent: Bot,
  memory: HardDrive,
  output: ArrowRight,
  mcp: Plug,
  tool_ext: Wrench,
}

const KIND_LABEL: Record<string, string> = {
  user: "USER",
  tool: "DATA",
  agent: "AGENT",
  memory: "MEMORY",
  output: "OUTPUT",
  mcp: "MCP SERVER",
  tool_ext: "TOOL",
}

// ---- designed multi-agent topology (hand-rolled SVG, 3-lane layout) ----
const W = 820
const NODE_W = 168
const NODE_H = 48
const VGAP = 22
const TOP = 26 // header band for lane labels
const LANE_TITLES = ["Sources", "Agents", "Sinks"]

function Topology({ nodes, edges }: { nodes: ModelNode[]; edges: ModelEdge[] }) {
  const lanes = [0, 1, 2].map((l) => nodes.filter((n) => n.lane === l))
  const laneX = [16, (W - NODE_W) / 2, W - NODE_W - 16]
  const rows = Math.max(1, ...lanes.map((l) => l.length))
  const H = rows * (NODE_H + VGAP) + 24 + TOP

  const pos: Record<string, { x: number; y: number }> = {}
  lanes.forEach((ns, li) => {
    const laneH = ns.length * (NODE_H + VGAP) - VGAP
    const startY = TOP + (H - TOP - laneH) / 2
    ns.forEach((n, i) => {
      pos[n.id] = { x: laneX[li], y: startY + i * (NODE_H + VGAP) }
    })
  })

  function path(s: { x: number; y: number }, t: { x: number; y: number }) {
    const forward = t.x > s.x + 4
    const sx = forward ? s.x + NODE_W : s.x
    const tx = forward ? t.x : t.x + NODE_W
    const sy = s.y + NODE_H / 2
    const ty = t.y + NODE_H / 2
    if (Math.abs(t.x - s.x) < 4) {
      const bow = s.x - 46
      return `M${s.x},${sy} C${bow},${sy} ${bow},${ty} ${t.x},${ty}`
    }
    const mx = (sx + tx) / 2
    return `M${sx},${sy} C${mx},${sy} ${mx},${ty} ${tx},${ty}`
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 460 }} role="img" aria-label="Multi-agent topology">
      <defs>
        <marker id="model-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill="context-stroke" />
        </marker>
      </defs>
      {laneX.map((x, li) =>
        lanes[li].length ? (
          <text
            key={`lane-${li}`}
            x={x + NODE_W / 2}
            y={15}
            textAnchor="middle"
            className="fill-muted-foreground"
            fontSize={9.5}
            fontWeight={600}
            letterSpacing={1}
          >
            {LANE_TITLES[li].toUpperCase()}
          </text>
        ) : null,
      )}
      {edges.map((e, i) => {
        const s = pos[e.source]
        const t = pos[e.target]
        if (!s || !t) return null
        const color = levelColor(e.level)
        return (
          <path
            key={i}
            d={path(s, t)}
            fill="none"
            stroke={color}
            strokeWidth={e.leaked ? 2.25 : 1.25}
            strokeOpacity={e.leaked ? 0.95 : 0.45}
            strokeDasharray={e.leaked ? "6 5" : e.channel === "inter_agent_message" ? undefined : "4 3"}
            markerEnd="url(#model-arrow)"
          >
            {e.leaked && (
              <animate attributeName="stroke-dashoffset" from="22" to="0" dur="0.9s" repeatCount="indefinite" />
            )}
            <title>{`${e.source} → ${e.target} · ${e.channel}${e.leaked ? " · LEAK" : ""}`}</title>
          </path>
        )
      })}
      {nodes.map((n) => {
        const p = pos[n.id]
        const leak = n.leak_level > 0
        const Icon = KIND_ICON[n.kind] ?? Bot
        return (
          <g key={n.id} transform={`translate(${p.x},${p.y})`}>
            <rect
              width={NODE_W}
              height={NODE_H}
              rx={9}
              className="fill-card"
              stroke={leak ? levelColor(n.leak_level) : "hsl(var(--border))"}
              strokeWidth={leak ? 1.75 : 1}
            />
            <g transform="translate(11,9)" className={leak ? "" : "text-muted-foreground"} style={leak ? { color: levelColor(n.leak_level) } : undefined}>
              <Icon width={12} height={12} />
            </g>
            <text x={30} y={16} className="fill-muted-foreground" fontSize={9}>
              {n.kind === "agent" && n.framework_label ? n.framework_label.toUpperCase() : KIND_LABEL[n.kind] ?? n.kind.toUpperCase()}
            </text>
            <text x={13} y={31} className="fill-foreground" fontSize={13} fontWeight={500}>
              {n.label.length > 19 ? n.label.slice(0, 18) + "…" : n.label}
            </text>
            {n.kind === "agent" && (
              <text x={13} y={43} className="fill-muted-foreground" fontSize={9}>
                {n.role}{n.has_endpoint ? " · live" : " · scripted"}
              </text>
            )}
            {leak && (
              <circle cx={NODE_W - 12} cy={12} r={4} fill={levelColor(n.leak_level)}>
                <title>Leak observed at L{n.leak_level}</title>
              </circle>
            )}
          </g>
        )
      })}
    </svg>
  )
}

function LeakPathCard({ path }: { path: LeakPath }) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded px-1.5 py-0.5 text-[11px] font-semibold ${badgeChipClass(LEVEL_BADGE[path.level] ?? "low")}`}>
          {path.level_label}
        </span>
        <span className="text-sm font-medium">{path.data_type}</span>
        <code className="font-mono text-xs text-muted-foreground">{path.value}</code>
        <span className="text-[11px] text-muted-foreground">
          · entered via <code className="font-mono">{path.entered_via ?? "unknown"}</code> · {path.leak_count} disclosure
          {path.leak_count === 1 ? "" : "s"}
          {path.agents.length > 0 && <> · agents {path.agents.join(", ")}</>}
        </span>
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-1 gap-y-2">
        {path.steps.map((s, i) => (
          <div key={s.event_id + i} className="flex items-center gap-1">
            {i > 0 && <ArrowRight className="size-3 shrink-0 text-muted-foreground" />}
            <span
              className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] ${
                s.kind === "leak" ? "border-transparent" : "border-border bg-muted/40"
              }`}
              style={s.kind === "leak" ? { background: `${levelColor(s.level)}1f`, color: levelColor(s.level) } : undefined}
            >
              <span className="font-medium">{s.source || "?"}</span>
              <span className="opacity-60">→</span>
              <code className="font-mono">{s.channel}</code>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function ModelView({ model }: { model: ProjectModel }) {
  if (!model.agents.length) {
    return (
      <Card className="p-10 text-center text-sm text-muted-foreground">
        No agents configured yet. Add agents in the <b className="text-foreground">Agents</b> tab to model the system.
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-medium">Designed topology</h3>
          {model.last_run ? (
            <span className="text-xs text-muted-foreground">
              Leaks overlaid from last run · <b className="text-foreground">{model.last_run.verdict}</b> · RI{" "}
              {model.last_run.risk_index.toFixed(3)} · {model.last_run.leaked_secrets} leaked
            </span>
          ) : (
            <span className="text-xs text-muted-foreground">Run the agents to overlay where data leaks.</span>
          )}
        </div>
        <Topology nodes={model.topology.nodes} edges={model.topology.edges} />
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-[11px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-5" style={{ background: levelColor(0) }} /> handoff / dataflow
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-0.5 w-5 animate-pulse" style={{ background: badgeColor("high") }} /> leaked path
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Sparkles className="size-3" /> live = real LLM · scripted = offline
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="text-muted-foreground/70">severity</span>
            {[1, 2, 3, 4].map((lvl) => (
              <span
                key={lvl}
                className="inline-flex items-center gap-0.5"
                title={`L${lvl} · ${LEVEL_BADGE[lvl]}`}
              >
                <span className="inline-block size-2.5 rounded-sm" style={{ background: levelColor(lvl) }} />
                <span className="font-mono">L{lvl}</span>
              </span>
            ))}
          </span>
        </div>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {model.agents.map((a) => {
          const Icon = KIND_ICON.agent
          return (
            <Card key={a.id} className="p-4">
              <div className="flex items-center gap-2">
                <Icon className="size-4 text-primary" />
                <span className="text-sm font-medium">{a.name}</span>
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                <span className="rounded bg-muted px-1.5 py-0.5">{a.framework_label}</span>
                <span>· {a.role}</span>
                <span>· {a.has_endpoint ? `live (${a.model})` : "scripted"}</span>
              </div>
              {a.description && <p className="mt-2 text-xs text-muted-foreground">{a.description}</p>}
              {a.tools.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {a.tools.map((t) => (
                    <span
                      key={t.name + (t.server ?? "")}
                      className="inline-flex items-center gap-1 rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground"
                    >
                      {t.kind === "mcp" ? <Plug className="size-2.5" /> : <Wrench className="size-2.5" />}
                      {t.name}
                      {t.kind === "mcp" && t.server ? ` · ${t.server}` : ""}
                    </span>
                  ))}
                </div>
              )}
            </Card>
          )
        })}
      </div>

      {model.leak_paths.length > 0 && (
        <Card className="p-5">
          <h3 className="mb-3 text-sm font-medium">Where the data leaks ({model.leak_paths.length})</h3>
          <div className="space-y-2.5">
            {model.leak_paths.map((p, i) => (
              <LeakPathCard key={i} path={p} />
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
