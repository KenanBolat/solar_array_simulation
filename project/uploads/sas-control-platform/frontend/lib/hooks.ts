import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import { apiGet, apiSend } from "./api";
import { useUiStore } from "./store";
import type {
  Alarm,
  AuditEntry,
  CommandResult,
  CommandTemplate,
  Device,
  DeviceState,
  HardwareReadiness,
  Measurement,
  Meta,
  Rack,
  RackDetail,
  ScenarioDetail,
  ScenarioRun,
  ScenarioRunEvent,
  ScenarioSummary,
  ValidationResult,
} from "./types";

const FAST = 2000; // live-ish poll for state that also streams over SSE
const SLOW = 15000;

export function useMeta(): UseQueryResult<Meta> {
  return useQuery({ queryKey: ["meta"], queryFn: () => apiGet<Meta>("/api/meta") });
}

export function useHardwareReadiness(): UseQueryResult<HardwareReadiness> {
  return useQuery({
    queryKey: ["hardware-readiness"],
    queryFn: () => apiGet<HardwareReadiness>("/api/hardware-readiness"),
    refetchInterval: SLOW,
  });
}

export function useRacks(): UseQueryResult<Rack[]> {
  return useQuery({ queryKey: ["racks"], queryFn: () => apiGet<Rack[]>("/api/racks") });
}

export function useRack(id: string): UseQueryResult<RackDetail> {
  return useQuery({
    queryKey: ["rack", id],
    queryFn: () => apiGet<RackDetail>(`/api/racks/${id}`),
    enabled: !!id,
  });
}

export function useDevices(rackId?: string): UseQueryResult<Device[]> {
  return useQuery({
    queryKey: ["devices", rackId ?? "all"],
    queryFn: () =>
      apiGet<Device[]>(`/api/devices${rackId ? `?rack_id=${rackId}` : ""}`),
    refetchInterval: FAST,
  });
}

export function useDevice(id: string): UseQueryResult<Device> {
  return useQuery({
    queryKey: ["device", id],
    queryFn: () => apiGet<Device>(`/api/devices/${id}`),
    enabled: !!id,
  });
}

export function useDeviceState(id: string): UseQueryResult<DeviceState> {
  return useQuery({
    queryKey: ["device-state", id],
    queryFn: () => apiGet<DeviceState>(`/api/devices/${id}/state`),
    enabled: !!id,
    refetchInterval: FAST,
  });
}

export function useDeviceCapabilities(id: string): UseQueryResult<CommandTemplate[]> {
  return useQuery({
    queryKey: ["device-caps", id],
    queryFn: () => apiGet<CommandTemplate[]>(`/api/devices/${id}/capabilities`),
    enabled: !!id,
  });
}

export function useMeasurements(
  id: string,
  windowKey: string
): UseQueryResult<Measurement[]> {
  return useQuery({
    queryKey: ["measurements", id, windowKey],
    queryFn: () =>
      apiGet<Measurement[]>(`/api/devices/${id}/measurements?window=${windowKey}`),
    enabled: !!id,
    refetchInterval: FAST,
  });
}

export function useAlarms(activeOnly = false): UseQueryResult<Alarm[]> {
  return useQuery({
    queryKey: ["alarms", activeOnly],
    queryFn: () => apiGet<Alarm[]>(`/api/alarms?active_only=${activeOnly}`),
    refetchInterval: SLOW,
  });
}

export function useAuditLog(limit = 200): UseQueryResult<AuditEntry[]> {
  return useQuery({
    queryKey: ["audit", limit],
    queryFn: () => apiGet<AuditEntry[]>(`/api/audit-log?limit=${limit}`),
    refetchInterval: SLOW,
  });
}

export function useScenarios(): UseQueryResult<ScenarioSummary[]> {
  return useQuery({
    queryKey: ["scenarios"],
    queryFn: () => apiGet<ScenarioSummary[]>("/api/scenarios"),
  });
}

export function useScenario(id: string): UseQueryResult<ScenarioDetail> {
  return useQuery({
    queryKey: ["scenario", id],
    queryFn: () => apiGet<ScenarioDetail>(`/api/scenarios/${id}`),
    enabled: !!id,
  });
}

export function useScenarioRuns(): UseQueryResult<ScenarioRun[]> {
  return useQuery({
    queryKey: ["scenario-runs"],
    queryFn: () => apiGet<ScenarioRun[]>("/api/scenario-runs"),
    refetchInterval: FAST,
  });
}

export function useRunEvents(runId: string): UseQueryResult<ScenarioRunEvent[]> {
  return useQuery({
    queryKey: ["run-events", runId],
    queryFn: () => apiGet<ScenarioRunEvent[]>(`/api/scenario-runs/${runId}/events`),
    enabled: !!runId,
    refetchInterval: FAST,
  });
}

// --- mutations ---

export function useSendCommand(deviceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { template_id: string; params?: Record<string, unknown>; confirmed?: boolean }) =>
      apiSend<CommandResult>(`/api/devices/${deviceId}/commands`, "POST", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["device-state", deviceId] });
      qc.invalidateQueries({ queryKey: ["audit"] });
    },
  });
}

export function useSetOutput(deviceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { enabled: boolean; confirmed: boolean }) =>
      apiSend<CommandResult>(`/api/devices/${deviceId}/output`, "POST", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["device-state", deviceId] });
      qc.invalidateQueries({ queryKey: ["devices"] });
    },
  });
}

export function useSafeShutdown(deviceId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiSend<CommandResult>(`/api/devices/${deviceId}/safe-shutdown`, "POST", {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["device-state", deviceId] }),
  });
}

export function useValidateScenario(id: string) {
  return useMutation({
    mutationFn: () => apiSend<ValidationResult>(`/api/scenarios/${id}/validate`, "POST", {}),
  });
}

export function useCreateScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      name: string;
      description?: string;
      nodes: unknown[];
      edges: unknown[];
    }) => apiSend<ScenarioSummary>("/api/scenarios", "POST", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scenarios"] }),
  });
}

export function useRunScenario(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { target_device_ids: string[]; dry_run: boolean; confirmed: boolean }) =>
      apiSend<ScenarioRun>(`/api/scenarios/${id}/run`, "POST", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scenario-runs"] }),
  });
}

export function useRunControl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, action }: { runId: string; action: "pause" | "resume" | "abort" }) =>
      apiSend(`/api/scenario-runs/${runId}/${action}`, "POST", {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["scenario-runs"] }),
  });
}

export function useAckAlarm() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (alarmId: string) => apiSend<Alarm>(`/api/alarms/${alarmId}/ack`, "POST", {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alarms"] }),
  });
}

/** Convenience: current role from the UI store (for permission gating). */
export function useRole() {
  return useUiStore((s) => s.role);
}
