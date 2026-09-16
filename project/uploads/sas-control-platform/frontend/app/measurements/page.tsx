"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Panel, PanelHeader, Button, Select } from "@/components/ui/kit";
import { TelemetryChart } from "@/components/TelemetryChart";
import { useDevices, useMeasurements } from "@/lib/hooks";
import { csvUrl } from "@/lib/api";
import { fmt } from "@/lib/utils";

const WINDOWS = ["5m", "30m", "1h", "24h"];

export default function MeasurementsPage() {
  const devices = useDevices();
  const [deviceId, setDeviceId] = useState("");
  const [windowKey, setWindowKey] = useState("30m");
  const measurements = useMeasurements(deviceId, windowKey);

  useEffect(() => {
    if (!deviceId && devices.data && devices.data.length > 0) setDeviceId(devices.data[0].id);
  }, [devices.data, deviceId]);

  const rows = (measurements.data ?? []).slice(-25).reverse();

  return (
    <div>
      <PageHeader
        title="Measurements"
        subtitle="Historical voltage, current and power telemetry"
        actions={
          <div className="flex items-center gap-2">
            <Select value={deviceId} onChange={(e) => setDeviceId(e.target.value)} className="w-48">
              {(devices.data ?? []).map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </Select>
            <Select value={windowKey} onChange={(e) => setWindowKey(e.target.value)}>
              {WINDOWS.map((w) => (
                <option key={w} value={w}>
                  {w}
                </option>
              ))}
            </Select>
            <a
              href={deviceId ? csvUrl(`/api/devices/${deviceId}/measurements.csv?window=${windowKey}`) : "#"}
              target="_blank"
              rel="noreferrer"
            >
              <Button variant="outline" size="sm" disabled={!deviceId}>
                <Download size={14} /> CSV
              </Button>
            </a>
          </div>
        }
      />

      <div className="space-y-4 p-6">
        <Panel>
          <PanelHeader eyebrow="Series" title="Voltage · Current · Power" />
          <div className="p-3">
            <TelemetryChart data={measurements.data ?? []} height={320} />
          </div>
        </Panel>

        <Panel>
          <PanelHeader eyebrow="Samples" title="Most recent rows" />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-hairline)] text-left text-xs text-[var(--color-ink-faint)]">
                  <Th>Timestamp (UTC)</Th>
                  <Th right>Voltage (V)</Th>
                  <Th right>Current (A)</Th>
                  <Th right>Power (W)</Th>
                  <Th>Output</Th>
                  <Th>Quality</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((m, i) => (
                  <tr key={i} className="border-b border-[var(--color-hairline)]/60">
                    <Td mono>{m.timestamp_utc.replace("T", " ").slice(0, 19)}</Td>
                    <Td mono right>
                      {fmt(m.voltage_v, 2)}
                    </Td>
                    <Td mono right>
                      {fmt(m.current_a, 3)}
                    </Td>
                    <Td mono right>
                      {fmt(m.power_w, 1)}
                    </Td>
                    <Td>{m.output_enabled ? "on" : "off"}</Td>
                    <Td>{m.quality_flag}</Td>
                  </tr>
                ))}
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-sm text-[var(--color-ink-faint)]">
                      No samples in this window yet.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Th({ children, right }: { children: React.ReactNode; right?: boolean }) {
  return <th className={`px-4 py-2 font-medium ${right ? "text-right" : ""}`}>{children}</th>;
}
function Td({
  children,
  mono,
  right,
}: {
  children: React.ReactNode;
  mono?: boolean;
  right?: boolean;
}) {
  return (
    <td
      className={`px-4 py-2 text-[var(--color-ink-dim)] ${mono ? "readout" : ""} ${
        right ? "text-right" : ""
      }`}
    >
      {children}
    </td>
  );
}
