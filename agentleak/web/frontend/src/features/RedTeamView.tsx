import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  FileWarning,
  Layers3,
  Loader2,
  Radio,
  RefreshCw,
  Server,
  Shield,
  ShieldCheck,
  Sparkles,
  Target,
  Wrench,
  Zap,
} from "lucide-react"
import {
  api,
  type AdversaryLevel,
  type RedTeamAttackResult,
  type RedTeamCatalog,
  type RedTeamMetrics,
  type RedTeamResult,
  type RedTeamSeverity,
  type Vertical,
} from "@/lib/api"
import { Card } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

interface Props {
  projectId: string
}

const VERTICALS: { value: Vertical; label: string }[] = [
  { value: "healthcare", label: "Healthcare" },
  { value: "finance", label: "Finance" },
  { value: "legal", label: "Legal" },
  { value: "hr", label: "HR" },
  { value: "customer_support", label: "Customer Support" },
]

const ADVERSARY_LEVELS: { value: AdversaryLevel; label: string; desc: string }[] = [
  { value: "A0", label: "A0 · Benign", desc: "Inadvertent leaks and unsafe defaults; no active attacker." },
  { value: "A1", label: "A1 · External", desc: "Prompt injection, role confusion, extraction and evasion." },
  { value: "A2", label: "A2 · Internal", desc: "Tool poisoning, RAG, memory and multi-agent compromise." },
]

const LOCAL_PRESETS = [
  { label: "Ollama", url: "http://localhost:11434/v1", model: "llama3.2" },
  { label: "LM Studio", url: "http://localhost:1234/v1", model: "" },
]

const STRATEGY_META: Record<string, { label: string; description: string }> = {
  basic: { label: "Direct baseline", description: "Original vulnerability probe without transformation." },
  "jailbreak-template": { label: "Jailbreak template", description: "Authority framing attempts to displace ordinary workflow rules." },
  "authoritative-markup": { label: "Authoritative markup", description: "Trusted-looking XML policy markup carries the probe." },
  base64: { label: "Base64 encoding", description: "Decode-and-execute behavior is tested across input filters." },
  hex: { label: "Hex encoding", description: "UTF-8 hexadecimal encoding tests normalization boundaries." },
  rot13: { label: "ROT13 encoding", description: "A reversible substitution disguises high-signal words." },
  leetspeak: { label: "Leetspeak", description: "Common numeric substitutions mutate the attack prompt." },
  homoglyph: { label: "Unicode homoglyphs", description: "Readable Unicode lookalikes exercise canonicalization." },
  crescendo: { label: "Crescendo multi-turn", description: "Four authored turns build context before the final extraction request." },
}

const SEVERITY_META: Record<RedTeamSeverity, { label: string; color: string; background: string }> = {
  critical: { label: "Critical", color: "hsl(var(--sev-l4))", background: "hsl(var(--sev-l4) / .055)" },
  high: { label: "High", color: "hsl(var(--sev-l3))", background: "hsl(var(--sev-l3) / .055)" },
  medium: { label: "Medium", color: "hsl(var(--sev-l2))", background: "hsl(var(--sev-l2) / .055)" },
  low: { label: "Low", color: "hsl(var(--sev-l1))", background: "hsl(var(--sev-l1) / .055)" },
  informational: { label: "Informational", color: "hsl(var(--muted-foreground))", background: "hsl(var(--muted) / .5)" },
}

function pct(value: number) {
  return `${Math.round(value * 100)}%`
}

function riskColor(rate: number) {
  if (rate >= 0.7) return "hsl(var(--sev-l4))"
  if (rate >= 0.35) return "hsl(var(--sev-l3))"
  if (rate > 0) return "hsl(var(--sev-l2))"
  return "hsl(var(--sev-ok))"
}

function SeverityCards({ attacks }: { attacks: RedTeamAttackResult[] }) {
  const vulnerable = attacks.filter((attack) => attack.success)
  const tiers: RedTeamSeverity[] = ["critical", "high", "medium", "low"]
  const defended = attacks.length - vulnerable.length
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {tiers.map((severity) => {
        const meta = SEVERITY_META[severity]
        const count = vulnerable.filter((attack) => attack.severity === severity).length
        return (
          <Card key={severity} className="relative overflow-hidden p-4" style={{ background: meta.background }}>
            <span className="absolute inset-y-0 left-0 w-1" style={{ background: meta.color }} />
            <div className="text-xs font-semibold" style={{ color: meta.color }}>{meta.label}</div>
            <div className="mt-2 font-mono text-3xl font-semibold tnum">{count}</div>
            <div className="mt-1 text-[11px] text-muted-foreground">successful attack{count === 1 ? "" : "s"}</div>
          </Card>
        )
      })}
      <Card className="relative overflow-hidden bg-sev-ok/[0.045] p-4">
        <span className="absolute inset-y-0 left-0 w-1 bg-sev-ok" />
        <div className="text-xs font-semibold text-sev-ok">Defended</div>
        <div className="mt-2 font-mono text-3xl font-semibold tnum">{defended}</div>
        <div className="mt-1 text-[11px] text-muted-foreground">attacks contained</div>
      </Card>
    </div>
  )
}

function DefensePosture({ metrics, attacks }: { metrics: RedTeamMetrics; attacks: RedTeamAttackResult[] }) {
  const defenseRate = 1 - metrics.overall_asr
  const successful = attacks.filter((attack) => attack.success).length
  const topChannel = metrics.clr_per_channel[0]
  const color = defenseRate >= 0.8 ? "hsl(var(--sev-ok))" : defenseRate >= 0.6 ? "hsl(var(--sev-l2))" : "hsl(var(--sev-l4))"
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border px-5 py-4">
        <div className="flex items-center gap-2 text-sm font-semibold"><Shield className="size-4" /> Defense posture</div>
        <p className="mt-1 text-xs text-muted-foreground">How often the agent prevented the adversary from leaking an expected field.</p>
      </div>
      <div className="grid items-center gap-5 p-5 sm:grid-cols-[170px_1fr]">
        <div className="relative mx-auto flex size-36 items-center justify-center rounded-full" style={{ background: `conic-gradient(${color} ${defenseRate * 360}deg, hsl(var(--muted)) 0deg)` }}>
          <div className="flex size-[112px] flex-col items-center justify-center rounded-full bg-card shadow-inner">
            <span className="font-mono text-3xl font-semibold tnum">{pct(defenseRate)}</span>
            <span className="text-[10px] uppercase tracking-wide text-muted-foreground">defended</span>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {[
            { label: "Attacks succeeded", value: successful, detail: `${pct(metrics.overall_asr)} ASR`, tone: successful ? "text-sev-l4" : "text-sev-ok" },
            { label: "Mean leakage", value: pct(metrics.mean_elr), detail: "vault fields exposed", tone: metrics.mean_elr ? "text-sev-l3" : "text-sev-ok" },
            { label: "Privacy score", value: Math.round(metrics.mean_privacy_score), detail: "mean AgentRisk score", tone: "text-primary" },
            { label: "Top exposure", value: topChannel ? pct(topChannel.leak_rate) : "0%", detail: topChannel?.channel ?? "no leaking channel", tone: topChannel?.leak_rate ? "text-sev-l3" : "text-sev-ok" },
          ].map((item) => (
            <div key={item.label} className="rounded-lg border border-border bg-muted/20 p-3">
              <div className={`font-mono text-xl font-semibold tnum ${item.tone}`}>{item.value}</div>
              <div className="mt-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{item.label}</div>
              <div className="mt-0.5 text-[10px] leading-snug text-muted-foreground">{item.detail}</div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}

function ChannelExposure({ metrics }: { metrics: RedTeamMetrics }) {
  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border px-5 py-4">
        <div className="flex items-center gap-2 text-sm font-semibold"><Radio className="size-4" /> Exposure surfaces</div>
        <p className="mt-1 text-xs text-muted-foreground">Channel Leakage Rate pinpoints where successful attacks surfaced.</p>
      </div>
      <div className="space-y-3 p-5">
        {metrics.clr_per_channel.map((channel) => (
          <div key={channel.channel}>
            <div className="mb-1.5 flex items-center gap-2 text-xs">
              <code className="min-w-0 flex-1 truncate font-mono">{channel.channel}</code>
              <span className="font-mono font-semibold tnum">{pct(channel.leak_rate)}</span>
              <span className="w-16 text-right text-[10px] text-muted-foreground">{channel.avg_leaked_fields.toFixed(1)} fields</span>
            </div>
            <div className="relative h-2 overflow-hidden rounded-full bg-muted">
              <div className="bar-grow absolute inset-y-0 left-0 rounded-full" style={{ width: pct(channel.leak_rate), background: `linear-gradient(90deg, ${riskColor(channel.leak_rate)}88, ${riskColor(channel.leak_rate)})` }} />
            </div>
          </div>
        ))}
        {!metrics.clr_per_channel.length && <div className="py-8 text-center text-xs text-muted-foreground">No channel exposure detected.</div>}
      </div>
    </Card>
  )
}

function AttackMethods({ attacks }: { attacks: RedTeamAttackResult[] }) {
  const methods = useMemo(() => {
    const groups = new Map<string, RedTeamAttackResult[]>()
    attacks.forEach((attack) => groups.set(attack.strategy_id, [...(groups.get(attack.strategy_id) ?? []), attack]))
    return [...groups.entries()].map(([id, items]) => ({
      id,
      items,
      successful: items.filter((item) => item.success).length,
      asr: items.filter((item) => item.success).length / Math.max(1, items.length),
    })).sort((a, b) => b.asr - a.asr)
  }, [attacks])

  return (
    <Card className="overflow-hidden">
      <div className="border-b border-border px-5 py-4">
        <div className="flex items-center gap-2 text-sm font-semibold"><Target className="size-4" /> Attack methods</div>
        <p className="mt-1 text-xs text-muted-foreground">Promptfoo-compatible delivery strategies ranked by attack success rate.</p>
      </div>
      <div className="grid gap-px bg-border [grid-template-columns:repeat(auto-fit,minmax(240px,1fr))]">
        {methods.map((method) => {
          const meta = STRATEGY_META[method.id] ?? { label: method.items[0].strategy_name, description: "Adversarial delivery method used in this batch." }
          return (
            <div key={method.id} className="bg-card p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="text-xs font-semibold">{meta.label}</div>
                <span className="font-mono text-xs font-semibold tnum" style={{ color: riskColor(method.asr) }}>{pct(method.asr)}</span>
              </div>
              <p className="mt-1.5 min-h-8 text-[10px] leading-relaxed text-muted-foreground">{meta.description}</p>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full" style={{ width: pct(method.asr), background: riskColor(method.asr) }} />
              </div>
              <div className="mt-2 text-[10px] text-muted-foreground">{method.successful}/{method.items.length} attacks succeeded · up to {Math.max(...method.items.map((item) => item.attack_turns))} turn(s)</div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}

function RiskCategories({ attacks }: { attacks: RedTeamAttackResult[] }) {
  const categories = useMemo(() => {
    const groups = new Map<string, RedTeamAttackResult[]>()
    attacks.forEach((attack) => groups.set(attack.attack_family_id, [...(groups.get(attack.attack_family_id) ?? []), attack]))
    return [...groups.entries()].map(([id, items]) => ({
      id,
      items: [...items].sort((a, b) => Number(b.success) - Number(a.success) || b.max_level - a.max_level),
      name: items[0].attack_family_name,
      description: items[0].attack_family_description,
      defended: items.filter((item) => !item.success).length,
      total: items.length,
    })).sort((a, b) => (a.defended / a.total) - (b.defended / b.total))
  }, [attacks])
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set(categories.filter((category) => category.defended < category.total).map((category) => category.id)))
  const totalDefended = attacks.filter((attack) => !attack.success).length

  function toggle(id: string) {
    setExpanded((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold"><Layers3 className="size-4" /> Risk categories</div>
          <p className="mt-1 text-xs text-muted-foreground">Open a category to inspect each probe and its stored execution trace.</p>
        </div>
        <div className="text-xs text-muted-foreground"><span className="font-mono font-semibold text-foreground tnum">{pct(totalDefended / Math.max(1, attacks.length))}</span> · {totalDefended}/{attacks.length} defended</div>
      </div>
      <Card className="divide-y divide-border overflow-hidden">
        {categories.map((category) => {
          const isExpanded = expanded.has(category.id)
          const defenseRate = category.defended / Math.max(1, category.total)
          return (
            <div key={category.id}>
              <button type="button" onClick={() => toggle(category.id)} className={`flex w-full items-center gap-3 p-4 text-left transition-colors hover:bg-muted/40 ${isExpanded ? "bg-muted/25" : ""}`}>
                {isExpanded ? <ChevronDown className="size-4 shrink-0 text-muted-foreground" /> : <ChevronRight className="size-4 shrink-0 text-muted-foreground" />}
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold">{category.name}</div>
                  <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{category.description}</p>
                </div>
                <div className="hidden w-36 items-center gap-2 sm:flex">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full" style={{ width: pct(defenseRate), background: defenseRate >= 0.8 ? "hsl(var(--sev-ok))" : defenseRate >= 0.5 ? "hsl(var(--sev-l2))" : "hsl(var(--sev-l4))" }} />
                  </div>
                </div>
                <div className="w-16 text-right">
                  <div className="font-mono text-sm font-semibold tnum" style={{ color: defenseRate >= 0.8 ? "hsl(var(--sev-ok))" : riskColor(1 - defenseRate) }}>{pct(defenseRate)}</div>
                  <div className="text-[9px] text-muted-foreground">{category.defended}/{category.total}</div>
                </div>
                {defenseRate === 1 ? <CheckCircle2 className="size-4 shrink-0 text-sev-ok" /> : <AlertTriangle className="size-4 shrink-0 text-sev-l4" />}
              </button>
              {isExpanded && (
                <div className="divide-y divide-border border-t border-border bg-muted/10">
                  {category.items.map((attack) => {
                    const meta = SEVERITY_META[attack.severity]
                    return (
                      <Link key={attack.run_id} to={`/runs/${attack.run_id}`} className="group flex items-center gap-3 px-4 py-3 pl-11 transition-colors hover:bg-muted/45">
                        <span className="size-2 shrink-0 rounded-full" style={{ background: attack.success ? meta.color : "hsl(var(--sev-ok))" }} />
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-xs font-semibold">{attack.attack_name}</span>
                            <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">{attack.attack_class_id}</code>
                          </div>
                          <p className="mt-0.5 truncate text-[10px] text-muted-foreground">{attack.strategy_name} · {attack.primary_channel} · {attack.plugin_ids.join(", ") || "AgentLeak taxonomy"}</p>
                        </div>
                        <div className="hidden text-right sm:block">
                          <div className="font-mono text-[10px] text-muted-foreground">RI {attack.risk_index.toFixed(3)}</div>
                          <div className="text-[9px] text-muted-foreground">score {Math.round(attack.privacy_score)}</div>
                        </div>
                        <span className={`rounded-full px-2 py-0.5 text-[9px] font-semibold ${attack.success ? "bg-sev-l4/10 text-sev-l4" : "bg-sev-ok/10 text-sev-ok"}`}>{attack.success ? "Vulnerable" : "Defended"}</span>
                        <ExternalLink className="size-3 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                      </Link>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </Card>
    </div>
  )
}

function VulnerabilityReport({ result }: { result: RedTeamResult }) {
  const attacks = result.attacks ?? []
  return (
    <div className="space-y-4">
      <SeverityCards attacks={attacks} />
      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <DefensePosture metrics={result.metrics} attacks={attacks} />
        <ChannelExposure metrics={result.metrics} />
      </div>
      <AttackMethods attacks={attacks} />
      <RiskCategories attacks={attacks} />
    </div>
  )
}

function RemediationReport({ attacks }: { attacks: RedTeamAttackResult[] }) {
  const vulnerable = [...attacks.filter((attack) => attack.success)].sort((a, b) => b.max_level - a.max_level || b.risk_index - a.risk_index)
  if (!vulnerable.length) {
    return (
      <Card className="flex items-center gap-4 border-sev-ok/25 bg-sev-ok/[0.045] p-6">
        <span className="flex size-11 items-center justify-center rounded-full bg-sev-ok/10 text-sev-ok"><ShieldCheck className="size-5" /></span>
        <div><div className="text-sm font-semibold">No red-team remediation required</div><p className="mt-1 text-xs text-muted-foreground">Every adversarial probe in this batch was contained on its expected leak channel.</p></div>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      <Card className="border-sev-l4/20 bg-sev-l4/[0.035] p-4">
        <div className="flex gap-3"><Wrench className="mt-0.5 size-4 shrink-0 text-sev-l4" /><p className="text-sm"><span className="font-semibold">Prioritized remediation plan.</span> Fix the highest-severity execution boundary first, then re-run the same batch to measure the defense-rate change.</p></div>
      </Card>
      {vulnerable.map((attack, index) => {
        const meta = SEVERITY_META[attack.severity]
        const recommendations = attack.recommendations.length ? attack.recommendations : [
          `Filter sensitive values before ${attack.primary_channel} receives the payload.`,
          `Add a regression scenario for ${attack.attack_name} and block releases when it succeeds.`,
        ]
        return (
          <Card key={attack.run_id} className="overflow-hidden">
            <div className="flex flex-wrap items-start gap-3 border-b border-border px-5 py-4">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full font-mono text-xs font-semibold" style={{ color: meta.color, background: meta.background }}>{index + 1}</span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold">{attack.attack_name}</h3><span className="rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase" style={{ color: meta.color, background: meta.background }}>{meta.label}</span></div>
                <p className="mt-1 text-xs text-muted-foreground">{attack.attack_description}</p>
              </div>
              <Link to={`/runs/${attack.run_id}`} className="inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs text-muted-foreground hover:bg-muted hover:text-foreground">Open evidence <ExternalLink className="size-3" /></Link>
            </div>
            <div className="grid gap-4 p-5 lg:grid-cols-[220px_1fr]">
              <div className="space-y-2 text-[11px]">
                <div className="flex justify-between gap-3"><span className="text-muted-foreground">Attack class</span><code className="font-mono">{attack.attack_class_id}</code></div>
                <div className="flex justify-between gap-3"><span className="text-muted-foreground">Boundary</span><code className="font-mono">{attack.primary_channel}</code></div>
                <div className="flex justify-between gap-3"><span className="text-muted-foreground">Risk Index</span><span className="font-mono">{attack.risk_index.toFixed(3)}</span></div>
                <div className="pt-1"><span className="text-muted-foreground">Exposed types</span><div className="mt-1 flex flex-wrap gap-1">{attack.leaked_types.map((type) => <code key={type} className="rounded bg-sev-l4/10 px-1.5 py-0.5 font-mono text-[9px] text-sev-l4">{type}</code>)}</div></div>
              </div>
              <ol className="space-y-2">
                {recommendations.map((recommendation, recommendationIndex) => (
                  <li key={`${recommendation}-${recommendationIndex}`} className="flex gap-2.5 text-xs leading-relaxed"><span className="mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full bg-primary/10 font-mono text-[9px] font-semibold text-primary">{recommendationIndex + 1}</span><span>{recommendation}</span></li>
                ))}
              </ol>
            </div>
          </Card>
        )
      })}
    </div>
  )
}

export function RedTeamView({ projectId }: Props) {
  const [vertical, setVertical] = useState<Vertical>("healthcare")
  const [adversaryLevel, setAdversaryLevel] = useState<AdversaryLevel>("A1")
  const [n, setN] = useState(10)
  const [mode, setMode] = useState<"live" | "scripted">("live")
  const [baseUrl, setBaseUrl] = useState("")
  const [model, setModel] = useState("")
  const [catalog, setCatalog] = useState<RedTeamCatalog | null>(null)
  const [pluginPreset, setPluginPreset] = useState("agent_core")
  const [strategyProfile, setStrategyProfile] = useState("balanced")
  const [selectedPlugins, setSelectedPlugins] = useState<string[]>([])
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RedTeamResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pluginGroups = useMemo(() => {
    const groups = new Map<string, NonNullable<RedTeamCatalog>["plugins"]>()
    for (const plugin of catalog?.plugins ?? []) groups.set(plugin.category, [...(groups.get(plugin.category) ?? []), plugin])
    return [...groups.entries()]
  }, [catalog])

  useEffect(() => {
    api.redTeamCatalog().then((nextCatalog) => {
      setCatalog(nextCatalog)
      setSelectedPlugins(nextCatalog.plugin_presets.find((preset) => preset.id === "agent_core")?.plugin_ids ?? [])
      setSelectedStrategies(nextCatalog.strategy_profiles.find((profile) => profile.id === "balanced")?.strategy_ids ?? ["basic"])
    }).catch((catalogError: unknown) => setError(catalogError instanceof Error ? catalogError.message : String(catalogError)))
  }, [])

  const choosePluginPreset = (presetId: string) => {
    setPluginPreset(presetId)
    const preset = catalog?.plugin_presets.find((item) => item.id === presetId)
    if (preset) setSelectedPlugins(preset.plugin_ids)
  }

  const chooseStrategyProfile = (profileId: string) => {
    setStrategyProfile(profileId)
    const profile = catalog?.strategy_profiles.find((item) => item.id === profileId)
    if (profile) setSelectedStrategies(profile.strategy_ids)
  }

  const togglePlugin = (pluginId: string) => {
    setPluginPreset("custom")
    setSelectedPlugins((current) => current.includes(pluginId) ? current.filter((item) => item !== pluginId) : [...current, pluginId])
  }

  const toggleStrategy = (strategyId: string) => {
    setStrategyProfile("custom")
    setSelectedStrategies((current) => current.includes(strategyId) ? current.filter((item) => item !== strategyId) : [...current, strategyId])
  }

  const run = async () => {
    setLoading(true)
    setError(null)
    try {
      const payload: Parameters<typeof api.runRedTeam>[1] = {
        vertical,
        adversary_level: adversaryLevel,
        n,
        mode,
        plugins: selectedPlugins,
        strategies: selectedStrategies,
      }
      if (baseUrl.trim()) payload.base_url = baseUrl.trim()
      if (model.trim()) payload.model = model.trim()
      setResult(await api.runRedTeam(projectId, payload))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold"><Shield className="size-5 text-sev-l4" /> Adversarial red team</h2>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">Attack the real agent across prompts, tools, memory, handoffs, logs and files. Each probe is scored, stored and linked to its full execution trace.</p>
        </div>
        {result && <button type="button" onClick={run} disabled={loading} className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50"><RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} /> Re-run batch</button>}
      </div>

      {!result && (
        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-6 py-5">
            <div><div className="flex items-center gap-2 text-sm font-semibold"><Sparkles className="size-4 text-sev-l3" /> Configure the attack campaign</div><p className="mt-1 text-xs text-muted-foreground">{catalog ? `${catalog.plugins.length} vulnerability plugins, ${catalog.attack_classes} attack classes, ${catalog.strategies.length} delivery strategies` : "Loading the attack catalog…"} across seven observable execution channels.</p></div>
            <span className="rounded-full bg-muted px-2.5 py-1 text-[10px] uppercase tracking-wide text-muted-foreground">results persist as project runs</span>
          </div>
          <div className="space-y-6 p-6">
            <div className="grid gap-5 md:grid-cols-3">
              <div className="space-y-1.5"><label className="text-xs font-semibold">Industry context</label><select value={vertical} onChange={(event) => setVertical(event.target.value as Vertical)} className="w-full rounded-md border bg-background px-3 py-2 text-sm">{VERTICALS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><p className="text-[10px] text-muted-foreground">Shapes the private vault and realistic task context.</p></div>
              <div className="space-y-1.5"><label className="text-xs font-semibold">Adversary capability</label><select value={adversaryLevel} onChange={(event) => setAdversaryLevel(event.target.value as AdversaryLevel)} className="w-full rounded-md border bg-background px-3 py-2 text-sm">{ADVERSARY_LEVELS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><p className="text-[10px] text-muted-foreground">{ADVERSARY_LEVELS.find((item) => item.value === adversaryLevel)?.desc}</p></div>
              <div className="space-y-1.5"><label className="text-xs font-semibold">Probe budget</label><div className="grid grid-cols-3 gap-1.5">{[5, 10, 20].map((value) => <button key={value} type="button" onClick={() => setN(value)} className={`rounded-md border px-3 py-2 font-mono text-sm transition-colors ${n === value ? "border-foreground bg-foreground text-background" : "hover:bg-muted"}`}>{value}</button>)}</div><p className="text-[10px] text-muted-foreground">More probes increase class coverage and API usage.</p></div>
            </div>

            <div className="space-y-3 rounded-lg border border-border bg-muted/10 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><div className="text-xs font-semibold">Vulnerability plugins</div><p className="mt-1 text-[10px] text-muted-foreground">What to test. The catalog maps high-signal Promptfoo plugin IDs to observable AgentLeak classes.</p></div>
                <div className="flex items-center gap-2"><span className="font-mono text-xs font-semibold">{selectedPlugins.length}/{catalog?.plugins.length ?? 0}</span><span className="text-[10px] text-muted-foreground">selected</span></div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {catalog?.plugin_presets.map((preset) => <button key={preset.id} type="button" title={preset.description} onClick={() => choosePluginPreset(preset.id)} className={`rounded-full border px-2.5 py-1 text-[10px] transition-colors ${pluginPreset === preset.id ? "border-foreground bg-foreground text-background" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}>{preset.name}</button>)}
              </div>
              <div className="grid gap-3 lg:grid-cols-2">
                {pluginGroups.map(([category, plugins]) => (
                  <div key={category} className="rounded-md border bg-background p-3">
                    <div className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{category}</div>
                    <div className="flex flex-wrap gap-1.5">
                      {plugins.map((plugin) => {
                        const active = selectedPlugins.includes(plugin.id)
                        return <button key={plugin.id} type="button" onClick={() => togglePlugin(plugin.id)} title={`${plugin.name}: ${plugin.description}`} className={`rounded border px-2 py-1 font-mono text-[9px] transition-colors ${active ? "border-primary/45 bg-primary/10 text-primary" : "border-border text-muted-foreground hover:text-foreground"}`}>{active ? "✓ " : ""}{plugin.id}</button>
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-3 rounded-lg border border-border bg-muted/10 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><div className="text-xs font-semibold">Attack strategies</div><p className="mt-1 text-[10px] text-muted-foreground">How to deliver each probe: direct, guardrail bypass, encoding, Unicode, or multi-turn escalation.</p></div>
                <span className="font-mono text-xs font-semibold">{selectedStrategies.length} selected</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {catalog?.strategy_profiles.map((profile) => <button key={profile.id} type="button" title={profile.description} onClick={() => chooseStrategyProfile(profile.id)} className={`rounded-full border px-2.5 py-1 text-[10px] transition-colors ${strategyProfile === profile.id ? "border-foreground bg-foreground text-background" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}>{profile.name}</button>)}
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {catalog?.strategies.map((strategy) => {
                  const active = selectedStrategies.includes(strategy.id)
                  return (
                    <button key={strategy.id} type="button" onClick={() => toggleStrategy(strategy.id)} className={`rounded-md border p-3 text-left transition-colors ${active ? "border-primary/45 bg-primary/[0.06]" : "hover:bg-muted/40"}`}>
                      <div className="flex items-center justify-between gap-2"><span className="text-xs font-semibold">{active ? "✓ " : ""}{strategy.name}</span><span className="font-mono text-[9px] text-muted-foreground">{strategy.estimated_turns}t</span></div>
                      <p className="mt-1 text-[10px] leading-relaxed text-muted-foreground">{strategy.description}</p>
                    </button>
                  )
                })}
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold">Execution mode</label>
              <div className="mt-2 grid gap-3 sm:grid-cols-2">
                <button type="button" onClick={() => setMode("live")} className={`rounded-lg border p-4 text-left transition-all ${mode === "live" ? "border-sev-l4/60 bg-sev-l4/[0.04] ring-1 ring-sev-l4/40" : "hover:bg-muted/40"}`}><div className="flex items-center gap-2 text-sm font-semibold"><Zap className="size-4 text-sev-l4" /> Live agent</div><p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">Runs each adversarial task through the configured agent or an OpenRouter-compatible endpoint. This measures real behavior.</p></button>
                <button type="button" onClick={() => setMode("scripted")} className={`rounded-lg border p-4 text-left transition-all ${mode === "scripted" ? "border-primary/50 bg-primary/[0.04] ring-1 ring-primary/30" : "hover:bg-muted/40"}`}><div className="flex items-center gap-2 text-sm font-semibold"><BarChart3 className="size-4" /> Scripted baseline</div><p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">Deterministic offline agent for validating detector coverage and creating a repeatable baseline.</p></button>
              </div>
            </div>

            {mode === "live" && (
              <div className="rounded-lg border bg-muted/20 p-4">
                <div className="flex flex-wrap items-center gap-2"><Server className="size-4 text-muted-foreground" /><span className="text-xs font-semibold">Optional endpoint override</span><span className="text-[10px] text-muted-foreground">Leave empty to use project settings or OPENROUTER_API_KEY.</span></div>
                <div className="mt-3 flex flex-wrap gap-1.5">{LOCAL_PRESETS.map((preset) => <button key={preset.label} type="button" onClick={() => { setBaseUrl(preset.url); if (preset.model) setModel(preset.model) }} className="rounded-full border px-2.5 py-1 text-[10px] text-muted-foreground hover:text-foreground">{preset.label}</button>)}</div>
                <div className="mt-2 grid gap-2 sm:grid-cols-2"><input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://openrouter.ai/api/v1" className="rounded-md border bg-background px-3 py-2 font-mono text-xs" /><input value={model} onChange={(event) => setModel(event.target.value)} placeholder="openai/gpt-4.1-mini" className="rounded-md border bg-background px-3 py-2 font-mono text-xs" /></div>
              </div>
            )}

            {error && <div className="flex gap-2 rounded-md border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive"><FileWarning className="mt-0.5 size-4 shrink-0" /> {error}</div>}
            <button type="button" onClick={run} disabled={loading || !catalog || !selectedPlugins.length || !selectedStrategies.length} className="inline-flex items-center gap-2 rounded-md bg-sev-l4 px-5 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50">{loading ? <Loader2 className="size-4 animate-spin" /> : <Zap className="size-4" />}{loading ? (mode === "live" ? `Running ${n} live probes…` : "Building baseline…") : `Launch ${n}-probe campaign`}</button>
          </div>
        </Card>
      )}

      {result && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border bg-muted/20 px-4 py-3 text-xs text-muted-foreground">
            <span>Target context <strong className="text-foreground">{VERTICALS.find((item) => item.value === result.vertical)?.label ?? result.vertical}</strong></span>
            <span>Capability <strong className="text-foreground">{result.adversary_level}</strong></span>
            <span><strong className="text-foreground">{result.scenarios_run}</strong> probes executed</span>
            <span><strong className="text-foreground">{result.coverage.plugins_exercised.length}</strong> plugins exercised</span>
            <span><strong className="text-foreground">{result.coverage.strategies_exercised.length}</strong> strategies exercised</span>
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${result.live ? "bg-sev-l4/10 text-sev-l4" : "bg-muted text-muted-foreground"}`}>{result.live ? "Live agent" : "Scripted baseline"}</span>
          </div>
          {result.coverage.plugins_not_exercised.length > 0 && (
            <div className="rounded-lg border border-sev-l2/25 bg-sev-l2/[0.045] px-4 py-3 text-xs">
              <span className="font-semibold">Coverage budget reached.</span>{" "}
              <span className="text-muted-foreground">Increase the probe budget or adversary capability to exercise: {result.coverage.plugins_not_exercised.join(", ")}.</span>
            </div>
          )}
          <Tabs defaultValue="vulnerabilities">
            <TabsList>
              <TabsTrigger value="vulnerabilities"><AlertTriangle className="size-3.5" /> Vulnerability report</TabsTrigger>
              <TabsTrigger value="remediation"><Wrench className="size-3.5" /> Remediation report</TabsTrigger>
            </TabsList>
            <TabsContent value="vulnerabilities"><VulnerabilityReport result={result} /></TabsContent>
            <TabsContent value="remediation"><RemediationReport attacks={result.attacks ?? []} /></TabsContent>
          </Tabs>
          <button type="button" onClick={() => setResult(null)} className="text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline">Configure a new campaign</button>
        </div>
      )}
    </div>
  )
}
