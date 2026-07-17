import { useMemo, useState } from "react"
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  Database,
  Eye,
  FileText,
  GitBranch,
  HardDrive,
  Network,
  Radio,
  Route,
  ScrollText,
  ShieldCheck,
  User,
  Zap,
} from "lucide-react"
import type { Badge as Sev } from "@/lib/api"
import { type Flow, type FlowEdge, type FlowNode, type LeakPath, type Report } from "@/lib/api"
import { badgeChipClass, badgeColor } from "@/lib/format"
import { Card } from "@/components/ui/card"

const LEVEL_BADGE: Record<number, Sev> = { 4: "critical", 3: "high", 2: "medium", 1: "low" }

function levelColor(level: number): string {
  return level > 0 ? badgeColor(LEVEL_BADGE[level] ?? "low") : "hsl(var(--muted-foreground) / 0.42)"
}

const KIND_META: Record<string, { label: string; icon: typeof Bot }> = {
  user: { label: "User", icon: User },
  tool: { label: "Tool / data", icon: Database },
  agent: { label: "Agent", icon: Bot },
  memory: { label: "Memory", icon: HardDrive },
  log: { label: "Log", icon: ScrollText },
  file: { label: "File", icon: FileText },
  external: { label: "External", icon: Radio },
  output: { label: "Output", icon: ArrowRight },
}

const LANE_META = [
  { label: "Sources", detail: "Where data enters" },
  { label: "Agent system", detail: "Reasoning and handoffs" },
  { label: "Destinations", detail: "Where data leaves" },
]

const CHANNEL_ACTION: Record<string, string> = {
  final_output: "Add an output redaction gate before the response reaches the user.",
  inter_agent_message: "Minimise handoff payloads and enforce a typed allow-list between agents.",
  tool_call: "Validate tool arguments and strip vault fields before every invocation.",
  shared_memory: "Store references instead of raw secrets and scope memory per task and agent.",
  log: "Apply structured log redaction before records reach the logger.",
  generated_file: "Scan generated artifacts before persistence or download.",
  external: "Restrict egress destinations and block sensitive fields at the network boundary.",
}

const W = 920
const NODE_W = 190
const NODE_H = 58
const ROW_GAP = 28
const LANE_X = [32, (W - NODE_W) / 2, W - NODE_W - 32]

function edgePath(source: { x: number; y: number }, target: { x: number; y: number }) {
  const sameLane = Math.abs(target.x - source.x) < 8
  const sourceY = source.y + NODE_H / 2
  const targetY = target.y + NODE_H / 2
  if (sameLane) {
    const bow = source.x - 54
    return `M ${source.x} ${sourceY} C ${bow} ${sourceY}, ${bow} ${targetY}, ${target.x} ${targetY}`
  }
  const forward = target.x > source.x
  const sourceX = forward ? source.x + NODE_W : source.x
  const targetX = forward ? target.x : target.x + NODE_W
  const midpoint = (sourceX + targetX) / 2
  return `M ${sourceX} ${sourceY} C ${midpoint} ${sourceY}, ${midpoint} ${targetY}, ${targetX} ${targetY}`
}

function nodeLabel(node: FlowNode) {
  return node.id.length > 23 ? `${node.id.slice(0, 22)}…` : node.id
}

function AgentDiagram({ flow }: { flow: Flow }) {
  const leakTarget = flow.edges.find((edge) => edge.leaked)?.target ?? null
  const [selectedNode, setSelectedNode] = useState<string | null>(leakTarget)
  const lanes = [0, 1, 2].map((lane) => flow.nodes.filter((node) => node.lane === lane))
  const rows = Math.max(1, ...lanes.map((lane) => lane.length))
  const H = Math.max(250, rows * (NODE_H + ROW_GAP) + 86)
  const positions: Record<string, { x: number; y: number }> = {}

  lanes.forEach((nodes, laneIndex) => {
    const laneHeight = nodes.length * NODE_H + Math.max(0, nodes.length - 1) * ROW_GAP
    const startY = 64 + Math.max(0, (H - 80 - laneHeight) / 2)
    nodes.forEach((node, index) => {
      positions[node.id] = { x: LANE_X[laneIndex], y: startY + index * (NODE_H + ROW_GAP) }
    })
  })

  const connected = (edge: FlowEdge) => !selectedNode || edge.source === selectedNode || edge.target === selectedNode
  const nodeLevel = (nodeId: string) => Math.max(0, ...flow.edges.filter((edge) => edge.target === nodeId && edge.leaked).map((edge) => edge.level))

  return (
    <div className="relative overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="min-w-[720px] w-full" style={{ maxHeight: 500 }} role="img" aria-label="Interactive agent data flow">
        <defs>
          <marker id="flow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="context-stroke" />
          </marker>
          <filter id="flow-glow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <linearGradient id="flow-lane" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="hsl(var(--muted) / .48)" />
            <stop offset="1" stopColor="hsl(var(--muted) / .08)" />
          </linearGradient>
        </defs>

        {LANE_X.map((laneX, index) => (
          <g key={LANE_META[index].label}>
            <rect x={laneX - 18} y={8} width={NODE_W + 36} height={H - 18} rx={16} fill="url(#flow-lane)" stroke="hsl(var(--border) / .65)" strokeDasharray="3 5" />
            <text x={laneX} y={31} className="fill-foreground" style={{ fontSize: 11, fontWeight: 650 }}>{LANE_META[index].label.toUpperCase()}</text>
            <text x={laneX} y={46} className="fill-muted-foreground" style={{ fontSize: 9 }}>{LANE_META[index].detail}</text>
          </g>
        ))}

        {flow.edges.map((edge, index) => {
          const source = positions[edge.source]
          const target = positions[edge.target]
          if (!source || !target) return null
          const focused = connected(edge)
          const color = levelColor(edge.level)
          const path = edgePath(source, target)
          return (
            <g key={`${edge.source}-${edge.target}-${edge.channel}-${index}`}>
              {edge.leaked && focused && <path d={path} fill="none" stroke={color} strokeWidth={8} strokeOpacity={0.1} filter="url(#flow-glow)" />}
              <path
                d={path}
                fill="none"
                stroke={color}
                strokeWidth={edge.leaked ? Math.min(4, 1.8 + Math.log2(edge.count + 1)) : 1.35}
                strokeOpacity={focused ? (edge.leaked ? 0.95 : 0.55) : 0.12}
                strokeDasharray={edge.leaked ? "8 6" : undefined}
                markerEnd="url(#flow-arrow)"
                className={edge.leaked && focused ? "flow-edge-leak" : "transition-opacity"}
              >
                <title>{`${edge.source} → ${edge.target} · ${edge.channel} · ${edge.count} event${edge.count === 1 ? "" : "s"}${edge.leaked ? ` · leak ${edge.level_label}` : " · clean"}`}</title>
              </path>
            </g>
          )
        })}

        {flow.nodes.map((node) => {
          const position = positions[node.id]
          const level = nodeLevel(node.id)
          const selected = selectedNode === node.id
          const affected = flow.edges.some((edge) => (edge.source === node.id || edge.target === node.id) && edge.leaked)
          const eventCount = flow.edges.filter((edge) => edge.source === node.id || edge.target === node.id).reduce((sum, edge) => sum + edge.count, 0)
          return (
            <g
              key={node.id}
              transform={`translate(${position.x},${position.y})`}
              role="button"
              tabIndex={0}
              aria-label={`Focus ${node.id}`}
              className="cursor-pointer outline-none"
              onClick={() => setSelectedNode(selected ? null : node.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") setSelectedNode(selected ? null : node.id)
              }}
            >
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={11}
                fill="hsl(var(--card))"
                stroke={selected ? "hsl(var(--foreground) / .7)" : affected ? levelColor(level || 2) : "hsl(var(--border))"}
                strokeWidth={selected ? 2 : affected ? 1.5 : 1}
                className="transition-all"
              />
              <circle cx={18} cy={19} r={5} fill={affected ? levelColor(level || 2) : "hsl(var(--muted-foreground) / .45)"} />
              {affected && <circle cx={18} cy={19} r={9} fill="none" stroke={levelColor(level || 2)} strokeOpacity={0.24} />}
              <text x={31} y={22} className="fill-muted-foreground" style={{ fontSize: 9, fontWeight: 600, letterSpacing: ".08em" }}>
                {(KIND_META[node.kind]?.label ?? node.kind).toUpperCase()}
              </text>
              <text x={14} y={43} className="fill-foreground" style={{ fontSize: 13, fontWeight: 650 }}>{nodeLabel(node)}</text>
              <text x={NODE_W - 12} y={43} textAnchor="end" className="fill-muted-foreground" style={{ fontSize: 9 }}>{eventCount} evt</text>
            </g>
          )
        })}
      </svg>
      <p className="mt-2 text-center text-[11px] text-muted-foreground">Select a node to isolate every incoming and outgoing route.</p>
    </div>
  )
}

function PathExplorer({ paths }: { paths: LeakPath[] }) {
  const [selectedIndex, setSelectedIndex] = useState(0)
  const selected = paths[selectedIndex]

  if (!paths.length) {
    return (
      <Card className="flex items-center gap-3 border-sev-ok/20 bg-sev-ok/[0.04] p-5">
        <span className="flex size-10 items-center justify-center rounded-full bg-sev-ok/10 text-sev-ok"><ShieldCheck className="size-5" /></span>
        <div>
          <div className="text-sm font-semibold">No secret propagation detected</div>
          <p className="mt-0.5 text-xs text-muted-foreground">The topology was captured, but no vault value crossed a disclosure boundary.</p>
        </div>
      </Card>
    )
  }

  const leakSteps = selected.steps.filter((step) => step.kind === "leak")
  const finalChannel = leakSteps[leakSteps.length - 1]?.channel ?? selected.channels[0]
  const action = CHANNEL_ACTION[finalChannel] ?? "Apply least-privilege data filtering at the last trusted boundary."

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-5 py-4">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold"><Route className="size-4 text-sev-l3" /> Secret propagation explorer</div>
          <p className="mt-1 text-xs text-muted-foreground">Follow one redacted value from its source to every disclosure.</p>
        </div>
        <span className="rounded-full bg-muted px-2.5 py-1 font-mono text-[11px] text-muted-foreground tnum">{paths.length} traced</span>
      </div>
      <div className="grid lg:grid-cols-[300px_1fr]">
        <div className="border-b border-border p-3 lg:border-b-0 lg:border-r">
          <div className="max-h-[380px] space-y-2 overflow-y-auto pr-1">
            {paths.map((path, index) => (
              <button
                type="button"
                key={`${path.data_type}-${index}`}
                onClick={() => setSelectedIndex(index)}
                className={`w-full rounded-lg border p-3 text-left transition-all ${index === selectedIndex ? "border-foreground/25 bg-muted/60 shadow-sm" : "border-transparent hover:bg-muted/35"}`}
              >
                <div className="flex items-center gap-2">
                  <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${badgeChipClass(LEVEL_BADGE[path.level] ?? "low")}`}>{path.level_label}</span>
                  <span className="min-w-0 flex-1 truncate text-xs font-semibold">{path.data_type}</span>
                  <ArrowRight className={`size-3 transition-transform ${index === selectedIndex ? "translate-x-0.5 text-foreground" : "text-muted-foreground"}`} />
                </div>
                <code className="mt-2 block truncate font-mono text-[11px] text-muted-foreground">{path.value}</code>
                <div className="mt-2 flex gap-3 text-[10px] text-muted-foreground">
                  <span>{path.leak_count} disclosure{path.leak_count === 1 ? "" : "s"}</span>
                  <span>{path.channels.length} channel{path.channels.length === 1 ? "" : "s"}</span>
                </div>
              </button>
            ))}
          </div>
        </div>

        <div className="p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${badgeChipClass(LEVEL_BADGE[selected.level] ?? "low")}`}>{selected.level_label}</span>
                <h3 className="text-sm font-semibold">{selected.data_type}</h3>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">Entered through <code className="font-mono text-foreground">{selected.entered_via ?? "unknown"}</code>{selected.agents.length ? ` · handled by ${selected.agents.join(", ")}` : ""}</p>
            </div>
            <code className="rounded-md bg-muted px-2 py-1 font-mono text-[11px] text-muted-foreground">{selected.value}</code>
          </div>

          <div className="mt-5 space-y-0">
            {selected.steps.map((step, index) => {
              const isLeak = step.kind === "leak"
              return (
                <div key={`${step.event_id}-${index}`} className="relative flex gap-3 pb-5 last:pb-1">
                  {index < selected.steps.length - 1 && <span className="absolute left-[15px] top-7 h-[calc(100%-16px)] w-px bg-border" />}
                  <span
                    className="relative z-10 flex size-8 shrink-0 items-center justify-center rounded-full border bg-card"
                    style={isLeak ? { borderColor: levelColor(step.level), color: levelColor(step.level), background: `${levelColor(step.level)}12` } : undefined}
                  >
                    {isLeak ? <AlertTriangle className="size-3.5" /> : <Database className="size-3.5 text-muted-foreground" />}
                  </span>
                  <div className="min-w-0 flex-1 pt-0.5">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="font-semibold">{isLeak ? "Disclosure" : "Trusted source"}</span>
                      <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px]">{step.channel}</code>
                    </div>
                    <p className="mt-1 truncate text-[11px] text-muted-foreground">{step.source || "unknown"} <ArrowRight className="mx-1 inline size-3" /> {step.target || "unknown"}</p>
                  </div>
                  {isLeak && <span className="font-mono text-[10px] font-semibold" style={{ color: levelColor(step.level) }}>{step.level_label}</span>}
                </div>
              )
            })}
          </div>

          <div className="mt-5 flex gap-3 rounded-lg border border-primary/20 bg-primary/[0.045] p-3">
            <Zap className="mt-0.5 size-4 shrink-0 text-primary" />
            <div>
              <div className="text-xs font-semibold">Best interception point · {finalChannel}</div>
              <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">{action}</p>
            </div>
          </div>
        </div>
      </div>
    </Card>
  )
}

export function FlowView({ report }: { report: Report }) {
  const flow = report.flow
  const paths = report.leak_paths ?? []

  const summary = useMemo(() => {
    if (!flow) return { leakEdges: 0, cleanEdges: 0, channels: 0 }
    const leakEdges = flow.edges.filter((edge) => edge.leaked).length
    return {
      leakEdges,
      cleanEdges: flow.edges.length - leakEdges,
      channels: new Set(flow.edges.map((edge) => edge.channel)).size,
    }
  }, [flow])

  if (!flow || flow.nodes.length === 0) {
    return (
      <Card className="p-10 text-center text-sm text-muted-foreground">
        No flow data for this run. Re-run it to capture the agent topology and leak paths.
      </Card>
    )
  }

  const highest = Math.max(0, ...paths.map((path) => path.level))
  const topPath = [...paths].sort((a, b) => b.level - a.level || b.leak_count - a.leak_count)[0]

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Participants", value: flow.nodes.length, icon: Network, tone: "text-primary" },
          { label: "Data routes", value: flow.edges.length, icon: GitBranch, tone: "text-primary" },
          { label: "Leaking routes", value: summary.leakEdges, icon: AlertTriangle, tone: summary.leakEdges ? "text-sev-l4" : "text-sev-ok" },
          { label: "Secrets traced", value: paths.length, icon: Eye, tone: paths.length ? "text-sev-l3" : "text-sev-ok" },
        ].map((item) => (
          <Card key={item.label} className="flex items-center gap-3 p-3.5">
            <span className={`flex size-9 items-center justify-center rounded-lg bg-muted ${item.tone}`}><item.icon className="size-4" /></span>
            <div><div className="font-mono text-xl font-semibold tnum">{item.value}</div><div className="text-[10px] uppercase tracking-wide text-muted-foreground">{item.label}</div></div>
          </Card>
        ))}
      </div>

      {topPath && (
        <Card className="border-sev-l3/20 bg-sev-l3/[0.035] p-4">
          <div className="flex gap-3">
            <AlertTriangle className="mt-0.5 size-4 shrink-0" style={{ color: levelColor(highest) }} />
            <p className="text-sm leading-relaxed">
              <span className="font-semibold">Primary exposure path. </span>
              <code className="font-mono text-xs">{topPath.data_type}</code> entered through {topPath.entered_via ?? "an unknown source"} and crossed {topPath.leak_count} disclosure {topPath.leak_count === 1 ? "boundary" : "boundaries"} across {topPath.channels.join(", ")}.
            </p>
          </div>
        </Card>
      )}

      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-5 py-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold"><Network className="size-4 text-primary" /> Live data-flow map</div>
            <p className="mt-1 text-xs text-muted-foreground">Animated routes reveal where trusted data becomes an exposure.</p>
          </div>
          <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1.5"><span className="inline-block h-0.5 w-4 bg-sev-l4" /> leak</span>
            <span className="flex items-center gap-1.5"><span className="inline-block h-px w-4 border-t border-dashed border-muted-foreground" /> clean</span>
            <span>{summary.channels} channels</span>
          </div>
        </div>
        <div className="p-4"><AgentDiagram flow={flow} /></div>
      </Card>

      <PathExplorer paths={paths} />
    </div>
  )
}
