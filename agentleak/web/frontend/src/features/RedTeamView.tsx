import { useState } from "react"
import { Shield, Zap, BarChart2, Target, ChevronDown, ChevronRight, Loader2, RefreshCw, Server } from "lucide-react"
import { api, type RedTeamResult, type RedTeamMetrics, type Vertical, type AdversaryLevel } from "../lib/api"

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
  { value: "A0", label: "A0 — Benign", desc: "Inadvertent leaks, no active attacker" },
  { value: "A1", label: "A1 — Weak", desc: "External injection via user/system prompt" },
  { value: "A2", label: "A2 — Strong", desc: "Controls tool outputs and shared memory" },
]

const LOCAL_PRESETS = [
  { label: "Ollama", url: "http://localhost:11434/v1", model: "llama3.2" },
  { label: "LM Studio", url: "http://localhost:1234/v1", model: "" },
]

function pct(v: number) {
  return `${Math.round(v * 100)}%`
}

function RiskBar({ value, max = 1, color = "bg-red-500" }: { value: number; max?: number; color?: string }) {
  const w = Math.min(100, (value / max) * 100)
  return (
    <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${w}%` }} />
    </div>
  )
}

function MetricsPanel({ metrics }: { metrics: RedTeamMetrics }) {
  const [showClasses, setShowClasses] = useState(false)

  return (
    <div className="space-y-6">
      {/* Top-line KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-lg border bg-card p-4 text-center">
          <div className="text-3xl font-bold text-red-500">{pct(metrics.overall_asr)}</div>
          <div className="text-xs text-muted-foreground mt-1">Attack Success Rate</div>
        </div>
        <div className="rounded-lg border bg-card p-4 text-center">
          <div className="text-3xl font-bold text-orange-500">{pct(metrics.mean_elr)}</div>
          <div className="text-xs text-muted-foreground mt-1">Mean Leakage Rate</div>
        </div>
        <div className="rounded-lg border bg-card p-4 text-center">
          <div className="text-3xl font-bold text-blue-500">{metrics.total_runs}</div>
          <div className="text-xs text-muted-foreground mt-1">Scenarios Run</div>
        </div>
        <div className="rounded-lg border bg-card p-4 text-center">
          <div className="text-3xl font-bold">
            {Math.round(metrics.mean_privacy_score)}
          </div>
          <div className="text-xs text-muted-foreground mt-1">Mean Privacy Score</div>
        </div>
      </div>

      {/* Channel leakage */}
      <div className="rounded-lg border bg-card p-4">
        <h3 className="font-semibold mb-3 flex items-center gap-2">
          <BarChart2 className="h-4 w-4 text-muted-foreground" />
          Channel Leakage Rate (CLR)
        </h3>
        <div className="space-y-3">
          {metrics.clr_per_channel.map((c) => (
            <div key={c.channel} className="space-y-1">
              <div className="flex justify-between text-sm">
                <span className="font-mono text-xs text-muted-foreground">{c.channel}</span>
                <span className="font-medium">{pct(c.leak_rate)}</span>
              </div>
              <RiskBar
                value={c.leak_rate}
                color={c.leak_rate > 0.5 ? "bg-red-500" : c.leak_rate > 0.2 ? "bg-orange-500" : "bg-yellow-500"}
              />
            </div>
          ))}
          {metrics.clr_per_channel.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-2">No channel data</p>
          )}
        </div>
      </div>

      {/* ASR by family */}
      <div className="rounded-lg border bg-card p-4">
        <h3 className="font-semibold mb-3 flex items-center gap-2">
          <Target className="h-4 w-4 text-muted-foreground" />
          ASR by Attack Family
        </h3>
        <div className="space-y-3">
          {metrics.asr_by_family.map((f) => (
            <div key={f.id} className="space-y-1">
              <div className="flex justify-between text-sm">
                <span>
                  <span className="font-mono font-bold text-xs mr-2">{f.id}</span>
                  <span className="text-muted-foreground text-xs">{f.name}</span>
                </span>
                <span className="text-xs">
                  {f.successful}/{f.total} — <strong>{pct(f.asr)}</strong>
                </span>
              </div>
              <RiskBar
                value={f.asr}
                color={f.asr > 0.7 ? "bg-red-500" : f.asr > 0.3 ? "bg-orange-500" : "bg-yellow-500"}
              />
            </div>
          ))}
        </div>

        {/* Toggle per-class */}
        {metrics.asr_by_class.length > 0 && (
          <button
            className="mt-3 text-xs flex items-center gap-1 text-muted-foreground hover:text-foreground"
            onClick={() => setShowClasses(!showClasses)}
          >
            {showClasses ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            {showClasses ? "Hide" : "Show"} per-class breakdown ({metrics.asr_by_class.length} classes)
          </button>
        )}
        {showClasses && (
          <div className="mt-3 space-y-2 border-t pt-3">
            {metrics.asr_by_class.map((c) => (
              <div key={c.id} className="flex justify-between text-xs">
                <span className="font-mono text-muted-foreground">{c.id}</span>
                <span className="text-muted-foreground">{c.name}</span>
                <span className="font-medium">{pct(c.asr)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Per-run ELR */}
      {metrics.elr_per_run.length > 0 && (
        <div className="rounded-lg border bg-card p-4">
          <h3 className="font-semibold mb-3 text-sm">Per-Run Exact Leakage Rate (ELR)</h3>
          <div className="overflow-auto max-h-48">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-muted-foreground text-left">
                  <th className="pb-2">Scenario</th>
                  <th className="pb-2 text-right">Leaked</th>
                  <th className="pb-2 text-right">ELR</th>
                </tr>
              </thead>
              <tbody>
                {metrics.elr_per_run.map((r) => (
                  <tr key={r.scenario_id} className="border-t">
                    <td className="py-1 font-mono text-muted-foreground truncate max-w-[200px]">{r.scenario_id}</td>
                    <td className="py-1 text-right">{r.leaked}/{r.total}</td>
                    <td className={`py-1 text-right font-medium ${r.elr > 0.3 ? "text-red-500" : r.elr > 0 ? "text-orange-500" : "text-green-500"}`}>
                      {pct(r.elr)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

export function RedTeamView({ projectId }: Props) {
  const [vertical, setVertical] = useState<Vertical>("healthcare")
  const [adversaryLevel, setAdversaryLevel] = useState<AdversaryLevel>("A1")
  const [n, setN] = useState(5)
  const [mode, setMode] = useState<"live" | "scripted">("live")
  const [baseUrl, setBaseUrl] = useState("")
  const [model, setModel] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<RedTeamResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = async () => {
    setLoading(true)
    setError(null)
    try {
      const payload: Parameters<typeof api.runRedTeam>[1] = {
        vertical, adversary_level: adversaryLevel, n, mode,
      }
      if (baseUrl.trim()) payload.base_url = baseUrl.trim()
      if (model.trim()) payload.model = model.trim()
      const res = await api.runRedTeam(projectId, payload)
      setResult(res)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Shield className="h-5 w-5 text-red-500" />
            Red Team
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Generate adversarial scenarios (6 attack families, 32 classes) and measure detection coverage.
          </p>
        </div>
        {result && (
          <button
            onClick={run}
            disabled={loading}
            className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-accent"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Re-run
          </button>
        )}
      </div>

      {/* Config */}
      {!result && (
        <div className="rounded-lg border bg-card p-6 space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {/* Vertical */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Vertical</label>
              <select
                value={vertical}
                onChange={(e) => setVertical(e.target.value as Vertical)}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              >
                {VERTICALS.map((v) => (
                  <option key={v.value} value={v.value}>{v.label}</option>
                ))}
              </select>
            </div>

            {/* Adversary level */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Adversary Level</label>
              <select
                value={adversaryLevel}
                onChange={(e) => setAdversaryLevel(e.target.value as AdversaryLevel)}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              >
                {ADVERSARY_LEVELS.map((a) => (
                  <option key={a.value} value={a.value}>{a.label}</option>
                ))}
              </select>
              <p className="text-xs text-muted-foreground">
                {ADVERSARY_LEVELS.find(a => a.value === adversaryLevel)?.desc}
              </p>
            </div>

            {/* N */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Scenarios (1–20)</label>
              <input
                type="number"
                min={1}
                max={20}
                value={n}
                onChange={(e) => setN(Math.min(20, Math.max(1, Number(e.target.value))))}
                className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              />
            </div>
          </div>

          {/* Execution mode */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Execution mode</label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setMode("live")}
                className={`rounded-md border px-4 py-3 text-left text-sm transition ${
                  mode === "live" ? "border-red-500 bg-red-500/5 ring-1 ring-red-500" : "hover:bg-accent"
                }`}
              >
                <div className="font-medium flex items-center gap-2">
                  <Zap className="h-4 w-4 text-red-500" /> Live agent
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Calls your real LLM endpoint (uses the configured agent or OPENROUTER_API_KEY).
                  Whether it leaks is the model's decision — a genuine audit.
                </p>
              </button>
              <button
                type="button"
                onClick={() => setMode("scripted")}
                className={`rounded-md border px-4 py-3 text-left text-sm transition ${
                  mode === "scripted" ? "border-primary bg-primary/5 ring-1 ring-primary" : "hover:bg-accent"
                }`}
              >
                <div className="font-medium">Scripted (offline)</div>
                <p className="text-xs text-muted-foreground mt-1">
                  Deterministic stand-in agent, no API key. Fast — measures detector coverage only.
                </p>
              </button>
            </div>
          </div>

          {/* Local endpoint override (visible only in live mode) */}
          {mode === "live" && (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Server className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-medium">Endpoint override</span>
                <span className="text-xs text-muted-foreground">(leave empty to use project Settings or OPENROUTER_API_KEY)</span>
              </div>
              <div className="flex flex-wrap gap-1.5 mb-2">
                {LOCAL_PRESETS.map((p) => (
                  <button
                    key={p.label}
                    type="button"
                    onClick={() => { setBaseUrl(p.url); if (p.model) setModel(p.model) }}
                    className="rounded-full border px-2.5 py-1 text-[11px] text-muted-foreground hover:border-foreground/30 hover:text-foreground"
                  >
                    {p.label}
                  </button>
                ))}
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <input
                  value={baseUrl}
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder="http://localhost:11434/v1"
                  className="rounded-md border bg-background px-3 py-2 text-xs font-mono"
                />
                <input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="llama3.2 (or any model name)"
                  className="rounded-md border bg-background px-3 py-2 text-xs font-mono"
                />
              </div>
            </div>
          )}

          {error && (
            <div className="rounded-md bg-destructive/10 text-destructive text-sm p-3">{error}</div>
          )}

          <button
            onClick={run}
            disabled={loading}
            className="flex items-center gap-2 rounded-md bg-red-600 px-5 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
            {loading ? (mode === "live" ? "Running live agent…" : "Running…") : "Launch Red Team"}
          </button>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
            <span>Vertical: <strong className="text-foreground">{result.vertical}</strong></span>
            <span>Level: <strong className="text-foreground">{result.adversary_level}</strong></span>
            <span>{result.scenarios_run} scenarios run</span>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                result.live ? "bg-red-500/10 text-red-500" : "bg-muted text-muted-foreground"
              }`}
            >
              {result.live ? "Live agent" : "Scripted"}
            </span>
          </div>
          <MetricsPanel metrics={result.metrics} />
          <button
            onClick={() => setResult(null)}
            className="text-xs text-muted-foreground hover:text-foreground underline"
          >
            Configure new run
          </button>
        </div>
      )}
    </div>
  )
}
