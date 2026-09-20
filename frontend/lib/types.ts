export type StatusColor = "faint" | "amber" | "cyan" | "green";

export interface Unit {
  name: string;
  /** How a channel is shown: "SAS-01 (@1)". */
  label: string;
  /** The mainframe this channel belongs to: "SAS-01". */
  instrument: string;
  rack: string;
  slot: number;
  pos: string;
  online: boolean;
  output: boolean;
  alarm: "normal" | "warning" | "offline";
  statusText: "OFFLINE" | "WARNING" | "ACTIVE" | "ONLINE";
  statusColor: StatusColor;
  voltage: number | null;
  current: number | null;
  power: number | null;
  voltageSetpoint: number;
  currentLimit: number;
  opMode: "FIX" | "SAS" | "TABL" | null;
  questionable: number;
  sas: SasCurve | null;
  mainframe: string;
  channel: number;
  transport: "auto" | "vxi11" | "socket";
  lastError: string | null;
  featured: boolean;
  enabled: boolean;
}

export interface SasCurve {
  isc: number;
  imp: number;
  vmp: number;
  voc: number;
}

export interface Preset extends SasCurve {
  id: number;
  name: string;
  mode: "FIX" | "SAS";
  enabled: boolean;
  note: string;
  volt: number;
  curr: number;
}

export interface Diagnosis {
  unit: string;
  ip: string;
  transport: string;
  from: { hostname: string; ips: string[] };
  checks: { check: string; ok: boolean; detail: string }[];
  recommend: "vxi11" | "socket" | null;
  verdict: string;
}

export interface Health {
  status: string;
  mode: string;
  fleetFile: string;
  units: number;
  emulatedUnits: number;
  emulators: number[];
  host: { hostname: string; ips: string[] };
  uiPort: number;
}

export interface SasProfile {
  name: string;
  voc: number;
  isc: number;
  vmp: number;
  imp: number;
  desc: string;
}

export interface UnitDetail extends Unit {
  connection: "CONNECTED" | "OFFLINE";
  ipAddress: string;
  macAddress: string;
  scpiPort: number;
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
  st: "OK" | "ERR" | "UNREACHABLE" | "TIMEOUT" | string;
  lat: string;
  rb: boolean;
  cid: string;
  scpi: string;
  resp: string;
  errCode: number | null;
  err: string;
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
  /** epoch milliseconds, one per sample */
  ts: number[];
  v: (number | null)[];
  i: (number | null)[];
  p: (number | null)[];
}

export interface MeasurementSeries {
  name: string;
  label: string;
  statusColor: StatusColor;
  /** epoch milliseconds, one per sample */
  ts: number[];
  v: (number | null)[];
  i: (number | null)[];
  p: (number | null)[];
}

export interface MeasurementRow {
  unit: string;
  time: string;
  v: number | null;
  i: number | null;
  p: number | null;
  out: string;
  q: "ok" | "no_reading";
}

export interface Measurements {
  series: MeasurementSeries[];
  rows: MeasurementRow[];
  count: number;
  sampleText: string;
}

export type NodeKind = "terminal" | "action" | "flow" | "measure" | "logic" | "danger";
/** ready = not run yet · running = in flight · done = finished ok · error = the
 *  instrument rejected it or comms failed · skipped = branch not taken */
export type NodeState = "ready" | "running" | "done" | "error" | "skipped";

export interface NodeParamSpec {
  key: string;
  label: string;
  /** "preset" and "unit" are selects whose options come from live data —
   *  the stored SAS presets, and the configured channels. */
  type: "number" | "select" | "preset" | "unit";
  unit?: string;
  options?: string[];
  default?: number | string;
  min?: number;
  max?: number;
  step?: number;
  /** Only shown when the block's `source` param equals this value. */
  only?: string;
}

export interface NodeTypeSpec {
  type: string;
  label: string;
  kind: NodeKind;
  badge: string;
  help: string;
  params: NodeParamSpec[];
}

export interface ScenarioNode {
  id: string;
  type: string;
  kind: NodeKind;
  badge: string;
  label: string;
  sub?: string;
  help?: string;
  x: number;
  y: number;
  params: Record<string, number | string>;
  /** The channel(s) this block will run against, following any Select Equipment
   *  blocks upstream of it. More than one means it is reachable down paths that
   *  selected different equipment. */
  runsOn: string[];
}

export interface ScenarioEdge {
  id: number;
  from: string;
  to: string;
  fail: boolean;
}

export interface ScenarioRunView {
  id: string;
  scenario: string;
  scenarioId: string;
  version: string;
  status: Run["status"];
  progress: number;
  targets: string[];
  by: string;
  started: string;
  finished: string;
  dur: string;
  currentNode: string | null;
  nodeStates: Record<string, NodeState>;
  startedMs: number | null;
  endedMs: number | null;
  estMs: number;
  /** Measured on the server, against the clock that stamped startedMs. */
  elapsedMs: number;
  stepsDone: number;
  stepsTotal: number;
  events: {
    t: string; node: string; lvl: RunEvent["lvl"]; m: string; scpi: string; resp: string; lat: number;
    /** the channel this step ran against */
    unit: string;
    /** ms from the run's start, or null for a step that was never stamped. */
    atMs: number | null;
  }[];
}

export interface ScenarioGraph {
  scenario: { id: string; name: string; version: string; state: string; targetUnit: string };
  nodes: ScenarioNode[];
  edges: ScenarioEdge[];
  nodeTypes: NodeTypeSpec[];
  /** problems block the run; warnings are worth reading but do not. */
  validation: { ok: boolean; problems: string[]; warnings: string[] };
  estMs: number;
  run: ScenarioRunView | null;
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
