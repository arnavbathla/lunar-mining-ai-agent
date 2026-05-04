export type ReadinessStatus = "pass" | "caution" | "fail";
export type MissionVerdict = "go" | "conditional_go" | "no_go";

export interface Mission {
  id: string;
  name: string;
  objective: string;
  duration_hours: number;
  target_resource: string;
  target_amount_kg: number;
  safety_battery_margin_pct: number;
  max_slope_deg: number;
  created_at: string;
}

export interface Cell {
  x: number;
  y: number;
  elevation_m: number;
  slope_deg: number;
  illumination_pct: number;
  resource_score: number;
  hazard_score: number;
  comms_quality: number;
  temperature_c: number;
  mineability_score: number;
}

export interface LunarSite {
  id: string;
  mission_id: string;
  name: string;
  region: string;
  grid_width: number;
  grid_height: number;
  cells_json: Cell[];
  created_at: string;
}

export interface Asset {
  id: string;
  mission_id: string;
  name: string;
  type: string;
  status: string;
  battery_kwh: number;
  max_battery_kwh: number;
  power_draw_kw: number;
  location_x: number;
  location_y: number;
  payload_kg: number;
  max_payload_kg: number;
  health_pct: number;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface Task {
  id: string;
  asset_id: string;
  asset_name: string;
  task_type: string;
  start_hour: number;
  end_hour: number;
  from_location?: { x: number; y: number } | null;
  to_location?: { x: number; y: number } | null;
  expected_output_kg: number;
  power_required_kwh: number;
  rationale: string;
  status: string;
}

export interface RiskItem {
  risk: string;
  severity: string;
  likelihood: string;
  mitigation: string;
}

export interface AutonomyArtifacts {
  behavior_tree: string;
  ros_task_messages: Record<string, unknown>[];
  state_machine: string;
  operator_runbook: string;
}

export interface Plan {
  id: string;
  mission_id: string;
  summary: string;
  tasks_json: Task[];
  risk_register_json: RiskItem[];
  expected_output_kg: number;
  confidence_pct: number;
  autonomy_artifacts_json: AutonomyArtifacts;
  created_at: string;
}

export interface ReadinessDimension {
  status: ReadinessStatus | MissionVerdict;
  explanation: string;
}

export interface ReadinessJSON {
  site_mineability: ReadinessDimension;
  production_target: ReadinessDimension;
  power_budget: ReadinessDimension;
  autonomy_risk: ReadinessDimension;
  mission_readiness: ReadinessDimension;
}

export interface SimulationRun {
  id: string;
  mission_id: string;
  plan_id: string;
  seed: number;
  status: string;
  total_output_kg: number;
  total_regolith_moved_kg: number;
  average_power_kw: number;
  lowest_battery_margin_pct: number;
  downtime_hours: number;
  anomaly_count: number;
  success_probability_pct: number;
  telemetry_json: TelemetryPoint[];
  readiness_json: ReadinessJSON | Record<string, never>;
  created_at: string;
}

export interface TelemetryPoint {
  hour: number;
  asset_id: string;
  asset_name: string;
  status: string;
  battery_pct: number;
  location_x: number;
  location_y: number;
  payload_kg: number;
  health_pct: number;
  power_kw: number;
  cumulative_output_kg: number;
  cumulative_regolith_moved_kg: number;
  alert_level: string;
}

export interface Anomaly {
  id: string;
  simulation_run_id: string;
  hour: number;
  asset_id?: string | null;
  type: string;
  severity: string;
  description: string;
  root_cause_hypothesis: string;
  recommended_action: string;
  production_impact_kg: number;
  requires_human_approval: boolean;
  created_at: string;
}

export interface Approval {
  id: string;
  anomaly_id: string;
  recommended_action: string;
  status: "pending" | "approved" | "rejected";
  operator_note: string;
  created_at: string;
  updated_at: string;
}

export interface SourceDocument {
  id: string;
  url: string;
  title: string;
  fetched_at: string;
  status: string;
  content_hash: string;
  raw_excerpt: string;
  extracted_facts_json: Record<string, string[]>;
  is_fallback: boolean;
}

export interface SourcesContext {
  last_refreshed_at: string | null;
  used_fallback: boolean;
  facts: Array<{
    category: string;
    fact: string;
    source_title: string;
    source_url: string;
    is_fallback: boolean;
  }>;
  sources: Array<{
    id: string;
    url: string;
    title: string;
    fetched_at: string;
    status: string;
    is_fallback: boolean;
  }>;
}

export interface DemoSeedOut {
  mission: Mission;
  site: LunarSite;
  assets: Asset[];
  sources_count: number;
  sources_used_fallback: boolean;
}

export interface DefaultDashboard {
  mission: Mission | null;
  site: LunarSite | null;
  assets: Asset[];
  latest_plan: Plan | null;
  latest_simulation: SimulationRun | null;
  anomalies: Anomaly[];
  sources: SourceDocument[];
}

export interface MissionBundle {
  mission: Mission;
  site: LunarSite | null;
  assets: Asset[];
  latest_plan: Plan | null;
  latest_simulation: SimulationRun | null;
  anomalies: Anomaly[];
}

export interface AgentToolCall {
  iteration: number;
  tool: string;
  input: Record<string, unknown>;
  output_summary: Record<string, unknown>;
  is_error: boolean;
}

export interface AgentStatus {
  anthropic_configured: boolean;
  model: string;
  available_agent_actions: string[];
}

export interface AgentReadinessResult {
  agent_run_id: string;
  tool_calls: AgentToolCall[];
  plan: Record<string, unknown> | null;
  simulation: Record<string, unknown> | null;
  readiness: ReadinessJSON | null;
  executive_recommendation: string;
  source_grounding_summary: string;
  next_actions: string[];
  model: string;
  created_at: string;
}

export interface AgentAnomalyResult {
  agent_run_id: string;
  tool_calls: AgentToolCall[];
  recommendation: {
    root_cause_hypothesis?: string;
    recommended_action?: string;
    alternative_actions?: string[];
    safety_impact?: string;
    production_impact_kg?: number;
    approval_required?: boolean;
    confidence_pct?: number;
  };
  approval_id: string | null;
  operator_message: string;
  model: string;
  created_at: string;
}

export interface AgentReportResult {
  agent_run_id: string;
  tool_calls: AgentToolCall[];
  report_id: string | null;
  markdown: string;
  model: string;
  created_at: string;
}
