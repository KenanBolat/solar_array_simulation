"use client";

import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import {
  Activity,
  Cpu,
  Pause,
  Play,
  Power,
  PowerOff,
  ShieldAlert,
  Terminal,
} from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Panel, PanelHeader, Badge, Button, Field, NumberInput, Select } from "@/components/ui/kit";
import { TelemetryChart } from "@/components/TelemetryChart";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { FrontPanel } from "@/components/FrontPanel";
import { CommandTerminal } from "@/components/CommandTerminal";
import {
  useDevice,
  useDeviceCapabilities,
  useDeviceState,
  useMeasurements,
  useRole,
  useSafeShutdown,
  useSendCommand,
  useSetOutput,
} from "@/lib/hooks";
import { useUiStore } from "@/lib/store";
import type { CommandResult, CommandTemplate } from "@/lib/types";
import { fmt, fmtTime, stateColor, stateLabel } from "@/lib/utils";

const WINDOWS = ["5m", "30m", "1h", "24h"];

export default function DeviceConsolePage() {
  const { id } = useParams<{ id: string }>();
  const device = useDevice(id);
  const state = useDeviceState(id);
  const caps = useDeviceCapabilities(id);
  const { chartsPaused, toggleChartsPaused } = useUiStore();
  const [windowKey, setWindowKey] = useState("5m");
  const measurements = useMeasurements(id, windowKey);

  const role = useRole();
  const canControl = role !== "observer";

  const s = state.data;
  const profile = device.data?.connection_profile;

  return (
    <div>
      <PageHeader
        title={device.data?.name ?? "Unit"}
        subtitle={
          profile
            ? `${profile.driver_kind.toUpperCase()} · ${profile.connection_type} · ${profile.name}`
            : "Loading unit…"
        }
        actions={
          s ? (
            <Badge color={stateColor(s.device_state)}>
              <span
                className="status-dot"
                style={{ color: stateColor(s.device_state), background: stateColor(s.device_state) }}
              />
              {stateLabel(s.device_state)}
            </Badge>
          ) : null
        }
      />

      <div className="grid grid-cols-1 gap-4 p-6 xl:grid-cols-3">
        {/* Live state + chart (spans 2) */}
        <div className="space-y-4 xl:col-span-2">
          <Panel>
            <PanelHeader
              eyebrow="Live"
              title="Telemetry"
              actions={
                <div className="flex items-center gap-1">
                  {WINDOWS.map((w) => (
                    <button
                      key={w}
                      onClick={() => setWindowKey(w)}
                      className="rounded px-2 py-1 text-xs"
                      style={
                        windowKey === w
                          ? { background: "var(--color-surface-3)", color: "var(--color-active)" }
                          : { color: "var(--color-ink-faint)" }
                      }
                    >
                      {w}
                    </button>
                  ))}
                  <Button size="sm" variant="ghost" onClick={toggleChartsPaused}>
                    {chartsPaused ? <Play size={13} /> : <Pause size={13} />}
                    {chartsPaused ? "Resume" : "Pause"}
                  </Button>
                </div>
              }
            />
            <div className="grid grid-cols-3 gap-px border-b border-[var(--color-hairline)] bg-[var(--color-hairline)]">
              <Readout label="Voltage" value={fmt(s?.voltage_v, 2)} unit="V" color="var(--color-active)" />
              <Readout label="Current" value={fmt(s?.current_a, 3)} unit="A" color="var(--color-output)" />
              <Readout label="Power" value={fmt(s?.power_w, 1)} unit="W" color="var(--color-scenario)" />
            </div>
            <div className="p-2">
              {chartsPaused ? (
                <div className="flex h-[260px] items-center justify-center text-sm text-[var(--color-ink-faint)]">
                  Chart paused
                </div>
              ) : (
                <TelemetryChart data={measurements.data ?? []} />
              )}
            </div>
          </Panel>

          <CommandTerminal deviceId={id} deviceName={device.data?.name ?? "Unit"} />

          <FrontPanel deviceId={id} deviceName={device.data?.name ?? "Unit"} />

          <CommandPanel deviceId={id} caps={caps.data ?? []} canControl={canControl} />
        </div>

        {/* Right column: identity + safe control */}
        <div className="space-y-4">
          <Panel>
            <PanelHeader eyebrow="Identity" title="Instrument" />
            <dl className="divide-y divide-[var(--color-hairline)] text-sm">
              <Row icon={<Cpu size={14} />} label="Firmware" value={s?.firmware ?? "—"} mono />
              <Row label="Device mode" value={s?.device_mode ?? "—"} />
              <Row label="Driver" value={profile?.driver_kind ?? "—"} mono />
              <Row label="Connection" value={profile?.connection_type ?? "—"} />
              <Row label="VISA resource" value={profile?.visa_resource || "—"} mono small />
              <Row label="Remote mode" value={s?.remote_mode ? "Remote" : "Local"} />
              <Row
                label="Comm health"
                value={s?.comm_health ?? "—"}
                valueColor={
                  s?.comm_health === "healthy"
                    ? "var(--color-online)"
                    : s?.comm_health === "lost"
                      ? "var(--color-alarm)"
                      : "var(--color-warning)"
                }
              />
              <Row label="Last comm" value={fmtTime(s?.last_comm_utc)} mono small />
            </dl>
          </Panel>

          <SafeControlPanel deviceId={id} outputEnabled={!!s?.output_enabled} canControl={canControl} />
        </div>
      </div>
    </div>
  );
}

// --- Safe control panel -----------------------------------------------------

function SafeControlPanel({
  deviceId,
  outputEnabled,
  canControl,
}: {
  deviceId: string;
  outputEnabled: boolean;
  canControl: boolean;
}) {
  const setOutput = useSetOutput(deviceId);
  const safeShutdown = useSafeShutdown(deviceId);
  const [confirm, setConfirm] = useState<null | "on" | "shutdown">(null);

  return (
    <Panel>
      <PanelHeader eyebrow="Safety" title="Output & shutdown" />
      <div className="space-y-3 p-4">
        <div className="flex items-center justify-between rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] px-3 py-2.5">
          <div className="flex items-center gap-2 text-sm">
            {outputEnabled ? (
              <Power size={15} style={{ color: "var(--color-output)" }} />
            ) : (
              <PowerOff size={15} className="text-[var(--color-ink-faint)]" />
            )}
            <span className="text-[var(--color-ink)]">Output</span>
            <Badge color={outputEnabled ? "var(--color-output)" : "var(--color-offline)"}>
              {outputEnabled ? "ENABLED" : "DISABLED"}
            </Badge>
          </div>
          {outputEnabled ? (
            <Button
              size="sm"
              variant="outline"
              disabled={!canControl || setOutput.isPending}
              onClick={() => setOutput.mutate({ enabled: false, confirmed: true })}
            >
              Disable
            </Button>
          ) : (
            <Button
              size="sm"
              variant="primary"
              disabled={!canControl || setOutput.isPending}
              onClick={() => setConfirm("on")}
            >
              Enable
            </Button>
          )}
        </div>

        <Button
          variant="danger"
          className="w-full"
          disabled={!canControl || safeShutdown.isPending}
          onClick={() => setConfirm("shutdown")}
        >
          <ShieldAlert size={15} /> Safe shutdown
        </Button>

        {!canControl ? (
          <p className="text-xs text-[var(--color-ink-faint)]">
            Your role is read-only. Switch to operator or above to control output.
          </p>
        ) : (
          <p className="text-xs text-[var(--color-ink-faint)]">
            Enabling output and safe shutdown require confirmation. Soft limits and
            hardware limits both apply; hardware limits are the ultimate authority.
          </p>
        )}
      </div>

      <ConfirmDialog
        open={confirm === "on"}
        title="Enable output"
        body="This will energise the output channel. Confirm the unit and downstream load are ready."
        confirmLabel="Enable output"
        onConfirm={() => {
          setOutput.mutate({ enabled: true, confirmed: true });
          setConfirm(null);
        }}
        onCancel={() => setConfirm(null)}
      />
      <ConfirmDialog
        open={confirm === "shutdown"}
        title="Safe shutdown"
        destructive
        requirePhrase="SHUTDOWN"
        body="Disables output and brings the unit to a safe state. Use this if the unit is behaving unexpectedly."
        confirmLabel="Execute shutdown"
        onConfirm={() => {
          safeShutdown.mutate();
          setConfirm(null);
        }}
        onCancel={() => setConfirm(null)}
      />
    </Panel>
  );
}

// --- Command execution panel ------------------------------------------------

function CommandPanel({
  deviceId,
  caps,
  canControl,
}: {
  deviceId: string;
  caps: CommandTemplate[];
  canControl: boolean;
}) {
  const send = useSendCommand(deviceId);
  const [templateId, setTemplateId] = useState("");
  const [params, setParams] = useState<Record<string, number>>({});
  const [pendingConfirm, setPendingConfirm] = useState(false);
  const [lastResult, setLastResult] = useState<CommandResult | null>(null);

  const template = useMemo(() => caps.find((t) => t.id === templateId), [caps, templateId]);

  function execute(confirmed: boolean) {
    if (!template) return;
    send.mutate(
      { template_id: template.id, params, confirmed },
      { onSuccess: (r) => setLastResult(r) }
    );
  }

  function onRun() {
    if (!template) return;
    if (template.requires_confirmation) setPendingConfirm(true);
    else execute(false);
  }

  return (
    <Panel>
      <PanelHeader
        eyebrow="Maintenance"
        title="Command execution"
        actions={
          <span className="flex items-center gap-1 text-xs text-[var(--color-ink-faint)]">
            <Terminal size={12} /> validated templates only
          </span>
        }
      />
      <div className="space-y-4 p-4">
        <Field label="Command template" hint="Raw SCPI is never exposed; only validated, named commands.">
          <Select
            value={templateId}
            onChange={(e) => {
              setTemplateId(e.target.value);
              setParams({});
              setLastResult(null);
            }}
            disabled={!canControl}
          >
            <option value="">Select a command…</option>
            {caps.map((t) => (
              <option key={t.id} value={t.id}>
                {t.title}
                {t.hazardous ? "  ⚠" : ""}
              </option>
            ))}
          </Select>
        </Field>

        {template ? (
          <div className="rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] p-3">
            <p className="text-xs text-[var(--color-ink-dim)]">{template.description}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {template.hazardous ? (
                <Badge color="var(--color-warning)">Hazardous</Badge>
              ) : (
                <Badge color="var(--color-online)">Read-only</Badge>
              )}
              {template.idempotent ? <Badge color="var(--color-offline)">Idempotent</Badge> : null}
              <Badge color={template.verified ? "var(--color-online)" : "var(--color-warning)"}>
                {template.verified ? "SCPI verified" : "SCPI unverified (mock)"}
              </Badge>
            </div>

            {Object.keys(template.parameters).length > 0 ? (
              <div className="mt-3 grid grid-cols-2 gap-3">
                {Object.entries(template.parameters).map(([name, spec]) => (
                  <Field
                    key={name}
                    label={`${name}${spec.unit ? ` (${spec.unit})` : ""}`}
                    hint={
                      spec.min !== undefined || spec.max !== undefined
                        ? `range ${spec.min ?? "−∞"}…${spec.max ?? "∞"}`
                        : undefined
                    }
                  >
                    <NumberInput
                      step="any"
                      min={spec.min}
                      max={spec.max}
                      value={params[name] ?? ""}
                      disabled={!canControl}
                      onChange={(e) =>
                        setParams((p) => ({ ...p, [name]: parseFloat(e.target.value) }))
                      }
                    />
                  </Field>
                ))}
              </div>
            ) : null}

            <div className="mt-3 flex justify-end">
              <Button
                variant={template.hazardous ? "warning" : "primary"}
                disabled={!canControl || send.isPending}
                onClick={onRun}
              >
                <Activity size={14} /> {send.isPending ? "Running…" : "Execute"}
              </Button>
            </div>
          </div>
        ) : null}

        {lastResult ? <ResultBlock result={lastResult} /> : null}
      </div>

      <ConfirmDialog
        open={pendingConfirm}
        title={`Confirm: ${template?.title ?? ""}`}
        body={
          <span>
            This is a hazardous command. It will be queued to the instrument and
            audited against your role.
          </span>
        }
        confirmLabel="Run command"
        onConfirm={() => {
          setPendingConfirm(false);
          execute(true);
        }}
        onCancel={() => setPendingConfirm(false)}
      />
    </Panel>
  );
}

function ResultBlock({ result }: { result: CommandResult }) {
  const ok = result.status === "completed";
  const color = ok
    ? "var(--color-output)"
    : result.status === "rejected" || result.status === "failed" || result.status === "timed_out"
      ? "var(--color-alarm)"
      : "var(--color-warning)";
  return (
    <div className="rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] p-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="status-dot" style={{ color, background: color }} />
        <span className="text-sm font-medium" style={{ color }}>
          {result.status.toUpperCase()}
        </span>
        <span className="ml-auto text-xs text-[var(--color-ink-faint)]">
          {result.latency_ms} ms · readback {result.readback_verified ? "✓" : "✗"}
        </span>
      </div>
      <div className="readout space-y-1 text-xs text-[var(--color-ink-dim)]">
        <div>
          <span className="text-[var(--color-ink-faint)]">sent </span>
          {result.scpi_sent ?? "—"}
        </div>
        <div>
          <span className="text-[var(--color-ink-faint)]">resp </span>
          {result.scpi_response ?? "—"}
        </div>
        {result.message ? (
          <div className="text-[var(--color-ink-faint)]">{result.message}</div>
        ) : null}
      </div>
    </div>
  );
}

// --- small presentational helpers ------------------------------------------

function Readout({
  label,
  value,
  unit,
  color,
}: {
  label: string;
  value: string;
  unit: string;
  color: string;
}) {
  return (
    <div className="bg-[var(--color-surface)] px-4 py-3">
      <div className="eyebrow">{label}</div>
      <div className="readout mt-1 flex items-baseline gap-1">
        <span className="text-2xl font-semibold" style={{ color }}>
          {value}
        </span>
        <span className="text-xs text-[var(--color-ink-faint)]">{unit}</span>
      </div>
    </div>
  );
}

function Row({
  icon,
  label,
  value,
  mono,
  small,
  valueColor,
}: {
  icon?: React.ReactNode;
  label: string;
  value: string;
  mono?: boolean;
  small?: boolean;
  valueColor?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2">
      <span className="flex items-center gap-2 text-xs text-[var(--color-ink-faint)]">
        {icon}
        {label}
      </span>
      <span
        className={`${mono ? "readout" : ""} ${small ? "text-[11px]" : "text-sm"} truncate text-right`}
        style={{ color: valueColor ?? "var(--color-ink)" }}
      >
        {value}
      </span>
    </div>
  );
}
