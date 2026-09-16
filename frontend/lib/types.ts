export type StatusColor = "faint" | "amber" | "cyan" | "green";

export interface Unit {
  name: string;
  rack: string;
  slot: number;
  pos: string;
  online: boolean;
  output: boolean;
  alarm: "normal" | "warning" | "offline";
  statusText: "OFFLINE" | "WARNING" | "ACTIVE" | "ONLINE";
  statusColor: StatusColor;
  voltage: number;
  current: number;
  power: number;
  voltageSetpoint: number;
  currentLimit: number;
  featured: boolean;
}

export interface UnitDetail extends Unit {
  connection: "CONNECTED" | "OFFLINE";
  visa: string;
  lastComm: string;
  firmware: string;
  mode: string;
  deviceState: string;
}

export interface Rack {
  id: string;
  name: string;
  loc: string;
  cap: number;
  count: number;
  onCount: number;
  units: Unit[];
}

export interface Summary {
  configuredUnits: number;
  onlineDevices: number;
  activeOutputs: number;
  totalPowerW: number;
  runningScenarios: number;
  activeAlarms: number;
  criticalAlarms: number;
}

export interface Alarm {
  id: number;
  time: string;
  unit: string;
  code: string;
  sev: "warning" | "critical" | "info";
  msg: string;
  active: boolean;
  ackd: boolean;
}

export interface HistoryRow {
  t: string;
  user: string;
  dev: string;
  tpl: string;
  st: "OK" | "WARN" | "ERR";
  lat: string;
  rb: boolean;
  cid: string;
}

export interface RunEvent {
  t: string;
  node: string;
  lvl: "ok" | "info" | "warn" | "err";
  m: string;
}

export interface Run {
  id: string;
  scenario: string;
  version: string;
  status: "Running" | "Completed" | "Aborted" | "Failed" | "Queued";
  dry: boolean;
  prog: number;
  targets: string[];
  by: string;
  started: string;
  finished: string;
  dur: string;
}

export interface RunDetail extends Run {
  events: RunEvent[];
}

export interface Telemetry {
  t: string;
  n: number;
  v: number[];
  i: number[];
  p: number[];
}

export interface MeasurementSeries {
  name: string;
  statusColor: StatusColor;
  v: number[];
  i: number[];
  p: number[];
}

export interface MeasurementRow {
  unit: string;
  time: string;
  v: number;
  i: number;
  p: number;
  out: string;
  q: "ok" | "interp" | "stale";
}

export interface Measurements {
  series: MeasurementSeries[];
  rows: MeasurementRow[];
  count: number;
  sampleText: string;
}

export interface ScenarioNode {
  id: string;
  type: string;
  label: string;
  sub?: string;
  x: number;
  y: number;
  kind: "terminal" | "action" | "flow" | "measure" | "logic" | "danger";
}

export interface ScenarioEdge {
  from: string;
  to: string;
  kind: "R" | "B";
  fail: boolean;
}

export interface ScenarioGraph {
  scenario: { id: string; name: string; version: string; state: string };
  nodes: ScenarioNode[];
  edges: ScenarioEdge[];
  palette: string[];
}

export interface NodeProps {
  name: string;
  target: string;
  params: [string, string][];
  delay: string;
  timeout: string;
  retry: string;
  fail: string;
  comments: string;
}

export interface TerminalCommand {
  name: string;
  aliases: string[];
  summary: string;
  effect?: string;
  usage?: string;
  hazardous: boolean;
  act: string;
  unit?: string;
  max?: number;
}
