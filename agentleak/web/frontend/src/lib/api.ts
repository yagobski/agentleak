export type LevelLabel = "L1" | "L2" | "L3" | "L4"
export type Badge = "critical" | "high" | "medium" | "low"

export const DETECTORS = ["pii", "secrets", "healthcare", "finance", "hr"] as const
export type DetectorId = (typeof DETECTORS)[number]
export const DETECTOR_LABEL: Record<DetectorId, string> = {
  pii: "PII",
  secrets: "Secrets",
  healthcare: "Healthcare",
  finance: "Finance",
  hr: "HR",
}

export interface Scenario {
  id: string
  name?: string
  domain: string
  description: string
  sensitive_data: string[]
  expected_behavior?: string[]
  example_trace?: string | null
  tags?: string[]
  difficulty?: string
  expected_outcome?: "leak" | "clean"
  topology?: "single_agent" | "multi_agent"
  attack_classes?: string[]
  source?: "builtin" | "custom" | "imported"
  builtin?: boolean
  pack_id?: string
  origin_id?: string
  has_spec?: boolean
}

export interface ScenarioDetail extends Scenario {
  trace: Record<string, unknown>
}

export interface ScenarioPack {
  id: string
  name: string
  description: string
  source: string
  format: string
  count: number
  imported_count: number
}

export interface ChannelRisk {
  channel: string
  level: Badge
  level_label: LevelLabel
  ri: number
  risk_contribution: number
  finding_count: number
}

export interface Finding {
  finding_id: string
  channel: string
  data_type: string
  severity: string
  level: number
  level_label: LevelLabel
  badge: Badge
  confidence: number
  redacted_value: string
  matched_value?: string
  detector: string
  recommendation: string
  source: string
  target: string
}

export interface Report {
  scoring: string
  project: string
  run_id: string
  agent_name: string
  scenario_id: string | null
  generated_at: string
  event_count: number
  privacy_score: number
  verdict: "Pass" | "Conditional pass" | "High risk" | "Fail"
  risk_index: number
  wsl: number
  rho_s: number
  scope_def: string
  blocked: boolean
  summary: {
    total_findings: number
    detected_total: number
    leaked_secrets: number
    vault_secrets: number
    level_profile: Record<LevelLabel, number>
    vault_level_profile: Record<LevelLabel, number>
    has_critical: boolean
  }
  channel_risks: ChannelRisk[]
  findings: Finding[]
  recommendations: string[]
  remediation_hints?: RemediationHint[]
  compliance: Compliance
  flow?: Flow
  leak_paths?: LeakPath[]
}

export interface RemediationHint {
  channel: string
  data_types: string[]
  priority: "critical" | "high" | "medium"
  advice: string
  code_fix: string
}

export interface CustomRule {
  name: string
  pattern: string
  severity: string
  data_type: string
}

export interface AnalyzePayload {
  trace?: unknown
  scenario_id?: string
  detectors?: Record<string, boolean>
  custom_detectors?: CustomRule[]
  vault?: { mode: "observed" | "explicit"; levels?: Record<string, number> }
  redact?: boolean
  privacy_policy?: {
    max_risk_index?: number
    max_findings?: number
    forbid_levels?: number[]
    forbid_channels?: string[]
    require_explicit_vault?: boolean
  }
}

export interface AgentEndpoint {
  base_url?: string
  model?: string
  api_key?: string
  api_key_set?: boolean
}

export interface ProjectConfig {
  detectors?: Record<string, boolean>
  vault?: { mode: "observed" | "explicit"; levels?: Record<string, number> }
  custom_detectors?: CustomRule[]
  redact?: boolean
  agent?: AgentEndpoint
  agents?: AgentConfig[]
}

export interface AgentConfig {
  id: string
  name: string
  role?: string
  framework: string
  description?: string
  endpoint?: AgentEndpoint
  tools?: ToolConfig[]
}

export interface ToolConfig {
  name: string
  kind: "function" | "mcp"
  server?: string
  description?: string
}

export interface Agent {
  id: string
  name: string
  role: string
  framework: string
  framework_label: string
  description: string
  has_endpoint: boolean
  model: string | null
  tools: ToolConfig[]
}

export interface AgentCardData {
  name: string
  description?: string
  capabilities: string[]
  tags?: string[]
  examples?: string[]
  input_mode?: string
  output_mode?: string
  agent_protocol_version?: string
  endpoints?: Record<string, string>
  framework?: string
  version?: string
  provider?: string
  url?: string
  privacy?: { declared_data_types?: string[] } & Record<string, unknown>
  source?: { type?: string; repo?: string; branch?: string } & Record<string, unknown>
}

export interface CodeFinding {
  file: string
  line: number
  rule: string
  data_type: string
  severity: string
  level: number
  snippet: string
  recommendation: string
  tier?: string
  confidence?: number
}

export interface CodeScanSummary {
  id: string
  project_id: string
  created_at: number
  source_type: string
  source_ref: string
  score: number
  verdict: string
  findings_count: number
}

export interface CodeScanDetail extends CodeScanSummary {
  result: {
    score: number
    verdict: string
    detection?: { mode: string; tiers: string[] }
    summary: {
      total_findings: number
      files_scanned: number
      files_skipped: number
      by_rule: Record<string, number>
      by_tier?: Record<string, number>
      level_profile: Record<string, number>
    }
    findings: CodeFinding[]
  }
}

export interface Project {
  id: string
  name: string
  agent_type: string
  description: string
  config: ProjectConfig
  agent_card?: AgentCardData | null
  created_at: number
  updated_at: number
  run_count?: number
  avg_risk_index?: number | null
  last_run?: RunSummary | null
}

export interface RunSummary {
  id: string
  project_id: string
  created_at: number
  source: string
  agent_name: string
  risk_index: number
  privacy_score: number
  verdict: Report["verdict"]
  blocked: boolean
  leaked_secrets: number
  label?: string
}

export interface Run extends RunSummary {
  report: Report
}

export interface Stats {
  projects: number
  runs: number
  avg_risk_index: number | null
  avg_privacy_score: number | null
  blocked_runs: number
  recent_runs: RunSummary[]
}

export interface AgentType {
  id: string
  label: string
}

export interface Meta {
  version: string
  channels: string[]
  detectors: string[]
  agent_types: AgentType[]
}

export interface ControlResult {
  id: string
  name: string
  status: "at_risk" | "ok" | "info" | "not_assessed"
  rationale: string
  evidence: string[]
  evidence_details: {
    finding_ids: string[]
    channels: string[]
    data_types: string[]
    levels: number[]
    policy_rules: string[]
  }
  assessment_basis: "trace_observation" | "trace_and_policy"
}

export interface FrameworkResult {
  id: string
  name: string
  url: string
  status: "compliant" | "non_compliant"
  at_risk: number
  not_assessed: number
  controls: ControlResult[]
}

export interface Compliance {
  frameworks: FrameworkResult[]
  summary: { total: number; compliant: number; non_compliant: number; controls_at_risk: number; controls_not_assessed: number }
  posture?: {
    status: "compliant" | "non_compliant"
    failed_frameworks: string[]
    failed: { id: string; name: string; at_risk: number }[]
  }
  assurance: {
    status: "observed_clear" | "controls_at_risk"
    evidence_grade: "trace_only" | "trace_and_policy"
    controls_not_assessed: number
    policy_assertions: string[]
  }
  evidence_matrix: { finding_id: string; frameworks: string[]; controls: string[] }[]
  integrity: {
    algorithm: "sha256"
    digest: string
    canonical_fields: string[]
    signed: false
    note: string
  }
}

export interface FlowNode {
  id: string
  kind: string
  lane: number
}

export interface FlowEdge {
  source: string
  target: string
  channel: string
  count: number
  leaked: boolean
  level: number
  level_label: string
}

export interface Flow {
  nodes: FlowNode[]
  edges: FlowEdge[]
}

export interface LeakStep {
  event_id: string
  channel: string
  source: string
  target: string
  kind: "source" | "leak"
  level: number
  level_label: string
}

export interface LeakPath {
  data_type: string
  value: string
  level: number
  level_label: string
  entered_via: string | null
  origin: LeakStep
  leak_count: number
  channels: string[]
  agents: string[]
  steps: LeakStep[]
}

export interface ModelNode {
  id: string
  kind: string
  lane: number
  label: string
  framework?: string
  framework_label?: string
  role?: string
  has_endpoint?: boolean
  leak_level: number
}

export interface ModelEdge {
  source: string
  target: string
  channel: string
  leaked: boolean
  level: number
}

export interface ProjectModel {
  agents: Agent[]
  topology: { nodes: ModelNode[]; edges: ModelEdge[] }
  last_run: { id: string; risk_index: number; verdict: Report["verdict"]; leaked_secrets: number } | null
  leak_paths: LeakPath[]
}

export interface ConnectInfo {
  framework: string
  snippet: string
  agents: { id: string; name: string; framework: string; framework_label: string; snippet: string }[]
}

// ----------- Red-team -------------------------------------------------

export interface RedTeamMetrics {
  total_runs: number
  total_scenarios: number
  mean_elr: number
  median_elr: number
  overall_asr: number
  mean_risk_index: number
  mean_privacy_score: number
  clr_per_channel: { channel: string; leak_rate: number; avg_leaked_fields: number }[]
  asr_by_family: { id: string; name: string; asr: number; successful: number; total: number }[]
  asr_by_class: { id: string; name: string; asr: number; successful: number; total: number }[]
  elr_per_run: { scenario_id: string; elr: number; leaked: number; total: number }[]
}

export type RedTeamSeverity = "critical" | "high" | "medium" | "low" | "informational"

export interface RedTeamAttackResult {
  run_id: string
  scenario_id: string
  attack_class_id: string
  attack_name: string
  attack_description: string
  attack_family_id: string
  attack_family_name: string
  attack_family_description: string
  injection_surface: string
  strategy_id: string
  strategy_name: string
  attack_turns: number
  plugin_ids: string[]
  primary_channel: string
  adversary_level: string
  success: boolean
  max_level: number
  severity: RedTeamSeverity
  risk_index: number
  privacy_score: number
  leaked_types: string[]
  leak_channels: string[]
  recommendations: string[]
}

export interface RedTeamResult {
  project_id: string
  vertical: string
  adversary_level: string
  mode: "live" | "scripted"
  live: boolean
  scenarios_run: number
  run_ids: string[]
  metrics: RedTeamMetrics
  attacks: RedTeamAttackResult[]
  coverage: {
    plugins_requested: string[]
    plugins_exercised: string[]
    plugins_not_exercised: string[]
    strategies_requested: string[]
    strategies_exercised: string[]
    plugin_preset: string
    strategy_profile: string
  }
}

export interface RedTeamPlugin {
  id: string
  name: string
  description: string
  category: string
  severity: RedTeamSeverity
  attack_classes: string[]
  requires: string[]
}

export interface RedTeamPluginPreset {
  id: string
  name: string
  description: string
  plugin_ids: string[]
}

export interface RedTeamStrategy {
  id: string
  name: string
  description: string
  category: string
  estimated_turns: number
}

export interface RedTeamStrategyProfile {
  id: string
  name: string
  description: string
  strategy_ids: string[]
}

export interface RedTeamCatalog {
  catalog_version: string
  attack_classes: number
  families: number
  plugins: RedTeamPlugin[]
  plugin_presets: RedTeamPluginPreset[]
  strategies: RedTeamStrategy[]
  strategy_profiles: RedTeamStrategyProfile[]
}

export type AdversaryLevel = "A0" | "A1" | "A2"
export type Vertical = "healthcare" | "finance" | "legal" | "hr" | "customer_support"

export interface RedTeamPayload {
  vertical?: Vertical
  n?: number
  adversary_level?: AdversaryLevel
  attack_class?: string
  mode?: "auto" | "live" | "scripted"
  base_url?: string
  model?: string
  plugins?: string[]
  plugin_preset?: string
  strategies?: string[]
  strategy_profile?: string
}

// ----------- Run history & progression --------------------------------

export interface RunHistoryEntry extends RunSummary {
  rank: number
  delta_score: number | null
  delta_ri: number | null
}

export interface Progression {
  first_score: number
  latest_score: number
  best_score: number
  best_run_id: string
  total_delta: number
  first_ri: number
  latest_ri: number
  total_runs: number
  blocked_runs: number
  direction: "improving" | "regressing" | "stable"
}

export interface RunHistory {
  runs: RunHistoryEntry[]
  progression: Progression | Record<string, never>
}

export interface FrameworkDiff {
  id: string
  before: string
  after: string
  change: "fixed" | "regressed" | "same"
}

export interface RunDiff {
  delta_score: number
  delta_ri: number
  delta_findings: number
  delta_leaked: number
  blocked_resolved: boolean
  score_direction: "improved" | "regressed" | "unchanged"
  frameworks: FrameworkDiff[]
}

export interface RunComparison {
  run_a: Run
  run_b: Run
  diff: RunDiff
}
export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

/** Event broadcast when any API call is rejected with 401 (expired session). */
export const UNAUTHORIZED_EVENT = "agentleak:unauthorized"

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* ignore */
    }
    if (res.status === 401 && typeof window !== "undefined") {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

export interface User {
  id: string
  email: string
  name: string
  created_at?: number
  is_admin?: boolean
}

export interface AdminUser extends User {
  disabled: boolean
  project_count: number
  run_count: number
}

export interface AdminOverview {
  users: number
  disabled_users: number
  admins: number
  projects: number
  runs: number
  avg_risk_index: number | null
  avg_privacy_score: number | null
  blocked_runs: number
  runs_24h: number
  blocked_24h: number
  active_projects_24h: number
  last_activity_at: number | null
  verdict_counts: Record<string, number>
  redteam_runs: number
  code_scans: number
  code_scans_24h: number
  api_calls_total: number
  api_calls_24h: number
  recent_runs: RunSummary[]
}

export interface AdminProjectUsage {
  id: string
  name: string
  owner_email: string
  run_count: number
  blocked_runs: number
  avg_risk_index: number | null
  avg_privacy_score: number | null
  last_run_at: number | null
  scan_count: number
  api_call_count: number
  last_api_call_at: number | null
}

export interface AdminDailyUsage {
  date: string
  runs: number
  blocked_runs: number
  api_calls: number
  code_scans: number
}

export interface AdminEndpointUsage {
  endpoint: string
  count: number
  projects: number
  last_called_at: number | null
}

export interface AdminUsage {
  projects: AdminProjectUsage[]
  daily: AdminDailyUsage[]
  endpoints: AdminEndpointUsage[]
}

export interface AuditLogEntry {
  id: string
  created_at: number
  actor_id: string
  actor_email: string
  action: string
  target_id: string
  target_email: string
  detail: string
}

export const api = {
  scenarios: () => jsonFetch<Scenario[]>("/api/scenarios"),
  scenario: (id: string) => jsonFetch<ScenarioDetail>(`/api/scenarios/${id}`),
  createScenario: (body: Record<string, unknown>) =>
    jsonFetch<Scenario>("/api/scenarios", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteScenario: (id: string) =>
    jsonFetch<{ deleted: boolean }>(`/api/scenarios/${id}`, { method: "DELETE" }),
  scenarioPacks: () => jsonFetch<ScenarioPack[]>("/api/scenario-packs"),
  importPack: (id: string) =>
    jsonFetch<{ imported: number; skipped: number; pack_id: string }>(
      `/api/scenario-packs/${id}/import`,
      { method: "POST" },
    ),
  example: (id: string) => jsonFetch<Record<string, unknown>>(`/api/example/${id}`),
  analyze: (payload: AnalyzePayload) =>
    jsonFetch<Report>("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  async report(fmt: "json" | "html" | "markdown", payload: AnalyzePayload): Promise<string> {
    const res = await fetch(`/api/report/${fmt}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    if (res.status === 401) { window.dispatchEvent(new Event(UNAUTHORIZED_EVENT)); throw new Error("Unauthorized") }
    if (!res.ok) throw new Error(await res.text())
    return res.text()
  },
  async render(fmt: "json" | "html" | "markdown", report: Report): Promise<string> {
    const res = await fetch(`/api/render/${fmt}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ report }),
    })
    if (res.status === 401) { window.dispatchEvent(new Event(UNAUTHORIZED_EVENT)); throw new Error("Unauthorized") }
    if (!res.ok) throw new Error(await res.text())
    return res.text()
  },
  meta: () => jsonFetch<Meta>("/api/meta"),

  // auth
  me: () => jsonFetch<User>("/api/auth/me"),
  register: (body: { email: string; password: string; name?: string }) =>
    jsonFetch<User>("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  login: (body: { email: string; password: string }) =>
    jsonFetch<User>("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  logout: () => jsonFetch<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  updateMe: (body: { name?: string }) =>
    jsonFetch<User>("/api/auth/me", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  changePassword: (body: { current_password: string; new_password: string }) =>
    jsonFetch<{ ok: boolean }>("/api/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteAccount: (body: { password: string }) =>
    jsonFetch<{ deleted: boolean }>("/api/auth/delete-account", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  // platform
  stats: () => jsonFetch<Stats>("/api/stats"),
  projects: () => jsonFetch<Project[]>("/api/projects"),
  project: (id: string) => jsonFetch<Project>(`/api/projects/${id}`),
  createProject: (body: Partial<Project> & { name: string }) =>
    jsonFetch<Project>("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  updateProject: (id: string, body: Record<string, unknown>) =>
    jsonFetch<Project>(`/api/projects/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  deleteProject: (id: string) => jsonFetch<{ deleted: boolean }>(`/api/projects/${id}`, { method: "DELETE" }),
  connect: (id: string) => jsonFetch<ConnectInfo>(`/api/projects/${id}/connect`),
  generateApiKey: (id: string) =>
    jsonFetch<{ api_key: string; project_id: string }>(`/api/projects/${id}/api-key`, { method: "POST" }),
  getApiKey: (id: string) =>
    jsonFetch<{ api_key: string | null; project_id: string; has_key: boolean }>(`/api/projects/${id}/api-key`),
  agents: (id: string) => jsonFetch<Agent[]>(`/api/projects/${id}/agents`),
  model: (id: string) => jsonFetch<ProjectModel>(`/api/projects/${id}/model`),
  addAgent: (id: string, body: Record<string, unknown>) =>
    jsonFetch<Project>(`/api/projects/${id}/agents`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  updateAgent: (id: string, aid: string, body: Record<string, unknown>) =>
    jsonFetch<Project>(`/api/projects/${id}/agents/${aid}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  removeAgent: (id: string, aid: string) =>
    jsonFetch<Project>(`/api/projects/${id}/agents/${aid}`, { method: "DELETE" }),
  projectRuns: (id: string) => jsonFetch<RunSummary[]>(`/api/projects/${id}/runs`),
  history: (id: string, limit = 100) =>
    jsonFetch<RunHistory>(`/api/projects/${id}/history?limit=${limit}`),
  compareRuns: (id: string, a: string, b: string) =>
    jsonFetch<RunComparison>(
      `/api/projects/${id}/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`,
    ),
  createRun: (id: string, body: AnalyzePayload & { source?: string; label?: string }) =>
    jsonFetch<Run>(`/api/projects/${id}/runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  executeAgent: (id: string, body: { scenario_id: string; mode?: "live" | "scripted"; label?: string }) =>
    jsonFetch<Run>(`/api/projects/${id}/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  run: (id: string) => jsonFetch<Run>(`/api/runs/${id}`),
  deleteRun: (id: string) => jsonFetch<{ deleted: boolean }>(`/api/runs/${id}`, { method: "DELETE" }),
  compare: (a: string, b: string) =>
    jsonFetch<{ a: Run; b: Run; dominance: "a" | "b" | "neither" }>("/api/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ a, b }),
    }),
  runRedTeam: (projectId: string, payload: RedTeamPayload) =>
    jsonFetch<RedTeamResult>(`/api/projects/${projectId}/redteam`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  redTeamCatalog: () => jsonFetch<RedTeamCatalog>("/api/redteam/catalog"),

  // agent card & code scans (agent-first layer)
  agentCard: (id: string) =>
    jsonFetch<{ project_id: string; agent_card: AgentCardData | null }>(`/api/projects/${id}/agent-card`),
  saveAgentCard: (id: string, card: AgentCardData) =>
    jsonFetch<{ project_id: string; agent_card: AgentCardData }>(`/api/projects/${id}/agent-card`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_card: card }),
    }),
  deleteAgentCard: (id: string) =>
    jsonFetch<{ deleted: boolean }>(`/api/projects/${id}/agent-card`, { method: "DELETE" }),
  fetchAgentCard: (id: string, url: string) =>
    jsonFetch<{ project_id: string; agent_card: AgentCardData }>(`/api/projects/${id}/agent-card/fetch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    }),
  runCodeScan: (id: string, payload: Record<string, unknown>) =>
    jsonFetch<CodeScanDetail>(`/api/projects/${id}/code-scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  codeScans: (id: string) => jsonFetch<CodeScanSummary[]>(`/api/projects/${id}/code-scans`),
  codeScan: (sid: string) => jsonFetch<CodeScanDetail>(`/api/code-scans/${sid}`),

  // admin console
  adminOverview: () => jsonFetch<AdminOverview>("/api/admin/overview"),
  adminUsers: () => jsonFetch<AdminUser[]>("/api/admin/users"),
  adminUpdateUser: (uid: string, body: { is_admin?: boolean; disabled?: boolean }) =>
    jsonFetch<AdminUser>(`/api/admin/users/${uid}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  adminDeleteUser: (uid: string) =>
    jsonFetch<{ deleted: boolean }>(`/api/admin/users/${uid}`, { method: "DELETE" }),
  adminAuditLog: () => jsonFetch<AuditLogEntry[]>("/api/admin/audit-log"),
  adminUsage: () => jsonFetch<AdminUsage>("/api/admin/usage"),
}
