import type {
  Alarm, Diagnosis, Health, HistoryRow, Measurements, Rack, RunDetail, Run, ScenarioGraph, NodeProps,
  Preset, SasCurve, SasProfile, Summary, Telemetry, Unit, UnitDetail,
} from "./types";

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    let detail: string | undefined;
    try {
      detail = JSON.parse(text)?.detail;
    } catch {
      // not JSON — fall through to the raw message below
    }
    throw new Error(detail || `${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const api = {
  summary: () => j<Summary>("/api/summary"),
  racks: () => j<Rack[]>("/api/racks"),
  units: () => j<Unit[]>("/api/units"),
  unit: (name: string) => j<UnitDetail>(`/api/units/${name}`),
  telemetry: (name: string, range: string) =>
    j<Telemetry>(`/api/units/${name}/telemetry?range=${encodeURIComponent(range)}`),
  setOutput: (name: string, on: boolean) =>
    j<{ unit: UnitDetail }>(`/api/units/${name}/output`, { method: "POST", body: JSON.stringify({ on }) }),
  setSetpoint: (name: string, body: { voltage?: number; currentLimit?: number }) =>
    j<{ unit: UnitDetail }>(`/api/units/${name}/setpoint`, { method: "POST", body: JSON.stringify(body) }),
  shutdown: (name: string) => j<{ unit: UnitDetail }>(`/api/units/${name}/shutdown`, { method: "POST" }),
  setMode: (name: string, mode: "FIX" | "SAS") =>
    j<{ unit: UnitDetail }>(`/api/units/${name}/mode`, { method: "POST", body: JSON.stringify({ mode }) }),
  clearProtection: (name: string) => j<{ unit: UnitDetail }>(`/api/units/${name}/clear-protection`, { method: "POST" }),
  setSasCurve: (name: string, body: SasCurve) =>
    j<{ unit: UnitDetail }>(`/api/units/${name}/sas-curve`, { method: "POST", body: JSON.stringify(body) }),
  saveState: (name: string, slot: number) =>
    j<{ unit: UnitDetail }>(`/api/units/${name}/state/save`, { method: "POST", body: JSON.stringify({ slot }) }),
  recallState: (name: string, slot: number) =>
    j<{ unit: UnitDetail }>(`/api/units/${name}/state/recall`, { method: "POST", body: JSON.stringify({ slot }) }),
  discoverChannels: () =>
    j<{ created: string[]; mainframes: { mainframe: string; channels: number | null; error: string | null }[] }>(
      "/api/units/discover-channels", { method: "POST" }),

  presets: () => j<{ presets: Preset[]; max: number }>("/api/presets"),
  createPreset: (body: Partial<Preset> & { name: string; mode: string }) =>
    j<Preset>("/api/presets", { method: "POST", body: JSON.stringify(body) }),
  enablePreset: (id: number, enabled: boolean) =>
    j<Preset>(`/api/presets/${id}/enable`, { method: "POST", body: JSON.stringify({ enabled }) }),
  deletePreset: (id: number) => j<{ ok: boolean }>(`/api/presets/${id}`, { method: "DELETE" }),
  applyPreset: (id: number, unit: string) =>
    j<{ unit: UnitDetail; preset: string }>(`/api/presets/${id}/apply`, { method: "POST", body: JSON.stringify({ unit }) }),
  reconnect: (name: string) => j<{ unit: UnitDetail; result: string }>(`/api/units/${name}/reconnect`, { method: "POST" }),
  resetConnections: () =>
    j<{ dropped: number; units: { name: string; online: boolean; transport: string; lastError: string | null }[] }>(
      "/api/units/reset-connections", { method: "POST" }),
  rebootUnit: (name: string) => j<{ unit: UnitDetail }>(`/api/units/${name}/reboot`, { method: "POST" }),
  diagnose: (name: string) => j<Diagnosis>(`/api/units/${name}/diagnose`, { method: "POST" }),
  health: () => j<Health>("/api/health"),
  refresh: (name: string) => j<{ unit: UnitDetail }>(`/api/units/${name}/refresh`, { method: "POST" }),
  identify: (name: string) => j<{ idn: string }>(`/api/units/${name}/identify`, { method: "POST" }),
  applyProfile: (name: string, profile: string) =>
    j<{ unit: UnitDetail }>(`/api/units/${name}/apply-profile`, { method: "POST", body: JSON.stringify({ profile }) }),
  terminalExecute: (name: string, act: string, label: string, value?: number) =>
    j<{ line: string; unit: Unit }>(`/api/units/${name}/terminal/execute`, {
      method: "POST", body: JSON.stringify({ act, value, label }),
    }),
  createUnit: (body: { name: string; rack: string; slot?: number; ipAddress?: string; macAddress?: string; scpiPort?: number; transport?: string; channel?: number; pollMs?: number }) =>
    j<UnitDetail>("/api/units", { method: "POST", body: JSON.stringify(body) }),
  deleteUnit: (name: string) => j<{ ok: boolean }>(`/api/units/${name}`, { method: "DELETE" }),
  enableUnit: (name: string) => j<UnitDetail>(`/api/units/${name}/enable`, { method: "POST" }),
  disableUnit: (name: string) => j<UnitDetail>(`/api/units/${name}/disable`, { method: "POST" }),
  updateNetwork: (name: string, body: { ipAddress?: string; macAddress?: string; scpiPort?: number; transport?: string; channel?: number }) =>
    j<UnitDetail>(`/api/units/${name}/network`, { method: "POST", body: JSON.stringify(body) }),

  measurements: (units: string[], range: string) =>
    j<Measurements>(`/api/measurements?units=${encodeURIComponent(units.join(","))}&range=${encodeURIComponent(range)}`),

  alarms: (filter: string) => j<{ rows: Alarm[]; activeCount: number; critCount: number }>(`/api/alarms?filter=${filter}`),
  ackAlarm: (id: number) => j<Alarm>(`/api/alarms/${id}/ack`, { method: "POST" }),

  history: (filter: string, limit = 200) =>
    j<{ rows: HistoryRow[]; total: number; shown: number }>(`/api/history?filter=${filter}&limit=${limit}`),

  runs: (filter: string) => j<Run[]>(`/api/runs?filter=${filter}`),
  run: (id: string) => j<RunDetail>(`/api/runs/${id}`),
  pauseRun: (id: string) => j<{ ok: boolean; message: string }>(`/api/runs/${id}/pause`, { method: "POST" }),
  abortRun: (id: string) => j<{ ok: boolean; message: string }>(`/api/runs/${id}/abort`, { method: "POST" }),

  scenario: (id: string) => j<ScenarioGraph>(`/api/scenarios/${id}`),
  nodeProps: (scenarioId: string, nodeId: string) => j<NodeProps>(`/api/scenarios/${scenarioId}/nodes/${nodeId}`),
  runScenario: (id: string) => j<RunDetail>(`/api/scenarios/${id}/run`, { method: "POST" }),

  configRacks: () => j<any[]>("/api/config/racks"),
  configUnits: () => j<any[]>("/api/config/units"),
  configLimits: () => j<any>("/api/config/limits"),
  configProfiles: () => j<SasProfile[]>("/api/config/profiles"),
  fleet: () => j<{ file: string; racks: any[]; units: any[] }>("/api/config/fleet"),
  applyFleet: () =>
    j<{ file: string; added: string[]; readdressed: string[]; unchanged: string[] }>(
      "/api/config/fleet/apply", { method: "POST" }),
  rackEditor: (rack = "A") => j<{ slots: any[]; palette: string[] }>(`/api/config/rack-editor?rack=${rack}`),
  assignUnit: (slot: string, unitName: string) =>
    j<{ assign: Record<string, string>; palette: string[] }>("/api/config/rack-editor/assign", {
      method: "POST", body: JSON.stringify({ slot, unitName }),
    }),
};

export const SCENARIO_ID = "eclipse-cycle-panel-a";
