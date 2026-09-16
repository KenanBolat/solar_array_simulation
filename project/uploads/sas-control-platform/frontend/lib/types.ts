// Types mirror the Pydantic response schemas in backend/app/schemas.
// They are intentionally explicit (no `any`) to satisfy strict mode.

export interface Meta {
  app_name: string;
  simulation_mode: boolean;
  hardware_enabled: boolean;
  capability_map_version: string;
  soft_limits: { max_voltage_v: number; max_current_a: number };
}

export interface Rack {
  id: string;
  name: string;
  location: string;
  position: number;
}

export interface ConnectionProfile {
  id: string;
  name: string;
  driver_kind: string;
  connection_type: string;
  visa_resource: string;
  fault_profile: string;
}

/** Cached last-known telemetry snapshot stored on the device row. */
export interface LastState {
  voltage_v?: number;
  current_a?: number;
  power_w?: number;
  output_enabled?: boolean;
  device_state?: string;
  alarm_state?: string | null;
  ts?: string;
}

export interface Device {
  id: string;
  name: string;
  rack_id: string;
  mainframe_id: string | null;
  module_id: string | null;
  channel_id: string | null;
  level: string;
  last_state: LastState;
  connection_profile: ConnectionProfile;
}

export interface Channel {
  id: string;
  index: number;
  name: string;
}
export interface Module {
  id: string;
  slot: number;
  name: string;
  channels: Channel[];
}
export interface Mainframe {
  id: string;
  name: string;
  model: string;
  modules: Module[];
}
export interface RackDetail extends Rack {
  mainframes: Mainframe[];
}

export interface DeviceState {
  device_id: string;
  connected: boolean;
  device_state: string;
  output_enabled: boolean;
  remote_mode: boolean;
  voltage_v: number;
  current_a: number;
  power_w: number;
  device_mode: string;
  alarm_state: string | null;
  firmware: string;
  last_comm_utc: string | null;
  comm_health: string;
  simulation: boolean;
}

export interface CommandTemplate {
  id: string;
  title: string;
  description: string;
  hazardous: boolean;
  requires_confirmation: boolean;
  idempotent: boolean;
  parameters: Record<string, ParameterSpec>;
  verified: boolean;
}

export interface ParameterSpec {
  type: string;
  min?: number;
  max?: number;
  unit?: string;
  required?: boolean;
}

export interface CommandResult {
  id: string;
  request_id: string;
  status: string;
  scpi_sent: string | null;
  scpi_response: string | null;
  readback_verified: boolean;
  message: string;
  latency_ms: number;
  started_utc: string;
  finished_utc: string;
}

export interface Measurement {
  timestamp_utc: string;
  voltage_v: number;
  current_a: number;
  power_w: number;
  output_enabled: boolean;
  device_state: string;
  quality_flag: string;
}

export interface Alarm {
  id: string;
  device_id: string;
  ts_utc: string;
  severity: string;
  code: string;
  message: string;
  acknowledged: boolean;
  acknowledged_by: string | null;
  cleared_utc: string | null;
}

export interface AuditEntry {
  id: string;
  ts_utc: string;
  actor: string;
  action: string;
  device_id: string | null;
  template_id: string | null;
  correlation_id: string;
  outcome: string;
  detail: Record<string, unknown>;
}

export interface ScenarioNode {
  node_key: string;
  type: string;
  label: string;
  x: number;
  y: number;
  config: Record<string, unknown>;
}

export interface ScenarioEdge {
  edge_key: string;
  source: string;
  target: string;
  label: string;
}

export interface ScenarioSummary {
  id: string;
  name: string;
  description: string;
  current_version: number;
  status?: string;
}

export interface ScenarioDetail extends ScenarioSummary {
  status: string;
  nodes: ScenarioNode[];
  edges: ScenarioEdge[];
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface ScenarioRun {
  id: string;
  scenario_id: string;
  version: number;
  status: string;
  dry_run: boolean;
  progress: number;
  started_utc: string | null;
  finished_utc: string | null;
  target_device_ids?: string[];
  started_by?: string;
}

export interface ScenarioRunEvent {
  ts_utc: string;
  node_key: string | null;
  level: string;
  message: string;
  id?: string;
  detail?: Record<string, unknown>;
}

export interface HardwareReadiness {
  simulation_mode: boolean;
  capability_map_version: string;
  operations: {
    op: string;
    verified: boolean;
    has_write: boolean;
    has_query: boolean;
    has_readback: boolean;
    note: string;
  }[];
  templates: {
    id: string;
    title: string;
    hazardous: boolean;
    live: boolean;
    blocked_by: string[];
  }[];
  gates: { id: string; label: string; ok: boolean; detail: string }[];
  summary: {
    verified_ops: number;
    total_ops: number;
    live_templates: number;
    total_templates: number;
    gates_open: number;
    total_gates: number;
  };
}

export type Role = "observer" | "operator" | "supervisor" | "administrator";
