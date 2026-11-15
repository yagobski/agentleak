// SPDX-FileCopyrightText: 2026 AgentLeak contributors
// SPDX-License-Identifier: MIT
import { useMemo, useState } from "react"
import { Plus, Trash2 } from "lucide-react"
import { type AnalyzePayload, type CustomRule, DETECTORS, DETECTOR_LABEL } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Switch } from "@/components/ui/switch"

const SEVERITY_BY_LEVEL: Record<string, string> = { "4": "critical", "3": "high", "2": "medium", "1": "low" }
const LEVEL_BY_SEVERITY: Record<string, string> = { critical: "4", high: "3", medium: "2", low: "1" }

export interface OptionsState {
  detectors: Record<string, boolean>
  rules: CustomRule[]
  vaultMode: "observed" | "explicit"
  vault: Record<1 | 2 | 3 | 4, number>
  redact: boolean
  gate: boolean
  maxRi: number
  maxFindings: number
  forbidL4: boolean
}

export const DEFAULT_OPTIONS: OptionsState = {
  detectors: Object.fromEntries(DETECTORS.map((d) => [d, true])),
  rules: [],
  vaultMode: "observed",
  vault: { 1: 0, 2: 0, 3: 0, 4: 0 },
  redact: true,
  gate: false,
  maxRi: 0.2,
  maxFindings: 0,
  forbidL4: true,
}

export function optionsToPayload(o: OptionsState): Omit<AnalyzePayload, "trace" | "scenario_id"> {
  const p: Omit<AnalyzePayload, "trace" | "scenario_id"> = { detectors: o.detectors, redact: o.redact }
  const rules = o.rules.filter((r) => r.name.trim() && r.pattern.trim()).map((r) => ({ ...r, data_type: r.name.trim() }))
  if (rules.length) p.custom_detectors = rules
  if (o.vaultMode === "explicit") p.vault = { mode: "explicit", levels: o.vault as unknown as Record<string, number> }
  if (o.gate) p.privacy_policy = { max_risk_index: o.maxRi, max_findings: o.maxFindings, forbid_levels: o.forbidL4 ? [4] : [] }
  return p
}

/** One line describing non-default settings, so a collapsed panel still says what will run. */
export function optionsSummary(o: OptionsState): string {
  const off = DETECTORS.filter((d) => !o.detectors[d])
  const parts = [off.length ? `${DETECTORS.length - off.length} of ${DETECTORS.length} detector families` : `all ${DETECTORS.length} detector families`]
  if (o.rules.some((r) => r.name && r.pattern)) parts.push(`${o.rules.filter((r) => r.name && r.pattern).length} custom rule(s)`)
  parts.push(o.vaultMode === "explicit" ? "explicit vault" : "observed vault")
  parts.push(o.redact ? "values masked in the report" : "raw values kept in the report")
  if (o.gate) parts.push(`gate RI ≤ ${o.maxRi}`)
  return parts.join(" · ")
}

export function AnalysisOptions({ value, onChange }: { value: OptionsState; onChange: (o: OptionsState) => void }) {
  const set = <K extends keyof OptionsState>(k: K, v: OptionsState[K]) => onChange({ ...value, [k]: v })
  const ids = useMemo(() => Math.random().toString(36).slice(2, 7), [])
  const [ruleError, setRuleError] = useState<Record<number, string>>({})

  function setRule(i: number, patch: Partial<CustomRule>) {
    const rules = value.rules.map((r, j) => (j === i ? { ...r, ...patch } : r))
    if (patch.pattern !== undefined) {
      try {
        new RegExp(patch.pattern)
        setRuleError((e) => ({ ...e, [i]: "" }))
      } catch {
        setRuleError((e) => ({ ...e, [i]: "Not a valid regular expression" }))
      }
    }
    set("rules", rules)
  }

  return (
    <div className="grid gap-6 text-sm md:grid-cols-2">
      <fieldset>
        <legend className="mb-2 text-[12px] font-medium text-muted-foreground">Detector families</legend>
        <div className="grid grid-cols-2 gap-x-4 gap-y-2">
          {DETECTORS.map((d) => (
            <label key={d} className="flex items-center justify-between gap-2">
              <span>{DETECTOR_LABEL[d]}</span>
              <Switch checked={value.detectors[d]} onCheckedChange={(v) => set("detectors", { ...value.detectors, [d]: v })} aria-label={`${DETECTOR_LABEL[d]} detector`} />
            </label>
          ))}
        </div>
        <label className="mt-4 flex items-center justify-between gap-2">
          <span>
            Mask values in the report
            <span className="block text-[11px] text-muted-foreground">Off writes raw matched values into the result.</span>
          </span>
          <Switch checked={value.redact} onCheckedChange={(v) => set("redact", v)} aria-label="Mask values in the report" />
        </label>
      </fieldset>

      <fieldset>
        <legend className="mb-2 text-[12px] font-medium text-muted-foreground">Vault scope (ρ_S, the denominator)</legend>
        <div className="flex gap-4" role="radiogroup">
          {(["observed", "explicit"] as const).map((m) => (
            <label key={m} className="inline-flex items-center gap-1.5">
              <input type="radio" name={`vault-${ids}`} className="accent-foreground" checked={value.vaultMode === m} onChange={() => set("vaultMode", m)} />
              {m === "observed" ? "Observed in the trace" : "Explicit counts"}
            </label>
          ))}
        </div>
        {value.vaultMode === "explicit" && (
          <div className="mt-2 grid grid-cols-4 gap-2">
            {([4, 3, 2, 1] as const).map((l) => (
              <label key={l} className="text-[11px] text-muted-foreground">
                L{l}
                <Input
                  type="number"
                  min={0}
                  value={value.vault[l]}
                  onChange={(e) => set("vault", { ...value.vault, [l]: Math.max(0, Number(e.target.value) || 0) })}
                  className="mt-1 h-8 font-mono text-xs"
                />
              </label>
            ))}
          </div>
        )}
        <p className="mt-1.5 text-[11px] text-muted-foreground">
          Observed uses every distinct value detected in the trace. Explicit counts give a stable denominator across runs.
        </p>
      </fieldset>

      <fieldset>
        <div className="mb-2 flex items-center justify-between">
          <legend className="text-[12px] font-medium text-muted-foreground">Custom rules</legend>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 text-[12px]"
            onClick={() => set("rules", [...value.rules, { name: "", pattern: "", severity: "high", data_type: "" }])}
          >
            <Plus /> Add rule
          </Button>
        </div>
        {value.rules.length === 0 && <p className="text-[12px] text-muted-foreground">Add a regex for internal identifiers the built-in detectors do not know.</p>}
        <ul className="space-y-2">
          {value.rules.map((r, i) => (
            <li key={i} className="grid grid-cols-[minmax(0,1fr)_4.5rem_2rem] gap-1.5">
              <Input value={r.name} onChange={(e) => setRule(i, { name: e.target.value })} placeholder="data type, e.g. project_code" aria-label="Rule name" className="h-8 text-xs" />
              <select
                value={LEVEL_BY_SEVERITY[r.severity] ?? "3"}
                onChange={(e) => setRule(i, { severity: SEVERITY_BY_LEVEL[e.target.value] })}
                aria-label="Rule level"
                className="h-8 rounded-md border border-input bg-background px-1 text-xs"
              >
                {["4", "3", "2", "1"].map((l) => (
                  <option key={l} value={l}>
                    L{l}
                  </option>
                ))}
              </select>
              <Button type="button" variant="ghost" size="icon" className="size-8" onClick={() => set("rules", value.rules.filter((_, j) => j !== i))} aria-label="Remove rule">
                <Trash2 className="size-3.5" />
              </Button>
              <Input
                value={r.pattern}
                onChange={(e) => setRule(i, { pattern: e.target.value })}
                placeholder="PROJ-[A-Z]{3}-\d{4}"
                aria-label="Rule pattern"
                aria-invalid={Boolean(ruleError[i])}
                className="col-span-3 h-8 font-mono text-xs"
              />
              {ruleError[i] && <p className="col-span-3 text-[11px] text-sev-l4">{ruleError[i]}</p>}
            </li>
          ))}
        </ul>
      </fieldset>

      <fieldset>
        <label className="mb-2 flex items-center justify-between gap-2">
          <span className="text-[12px] font-medium text-muted-foreground">Evaluation gate</span>
          <Switch checked={value.gate} onCheckedChange={(v) => set("gate", v)} aria-label="Evaluation gate" />
        </label>
        {value.gate ? (
          <div className="grid grid-cols-2 gap-2">
            <label className="text-[11px] text-muted-foreground">
              Max Risk Index
              <Input type="number" min={0} max={1} step={0.05} value={value.maxRi} onChange={(e) => set("maxRi", Math.min(1, Math.max(0, Number(e.target.value) || 0)))} className="mt-1 h-8 font-mono text-xs" />
            </label>
            <label className="text-[11px] text-muted-foreground">
              Max findings
              <Input type="number" min={0} value={value.maxFindings} onChange={(e) => set("maxFindings", Math.max(0, Number(e.target.value) || 0))} className="mt-1 h-8 font-mono text-xs" />
            </label>
            <label className="col-span-2 flex items-center justify-between gap-2 text-[13px]">
              Fail on any L4 disclosure
              <Switch checked={value.forbidL4} onCheckedChange={(v) => set("forbidL4", v)} aria-label="Fail on any L4 disclosure" />
            </label>
          </div>
        ) : (
          <p className="text-[12px] text-muted-foreground">Off: the result reports the engine's own blocking rule only.</p>
        )}
      </fieldset>
    </div>
  )
}
