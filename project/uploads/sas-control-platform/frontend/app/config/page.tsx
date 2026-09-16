"use client";

import { PageHeader } from "@/components/PageHeader";
import { Panel, PanelHeader, Badge } from "@/components/ui/kit";
import { useDevices, useMeta } from "@/lib/hooks";

export default function ConfigPage() {
  const meta = useMeta();
  const devices = useDevices();

  return (
    <div>
      <PageHeader
        title="Device Configuration"
        subtitle="Connection profiles, soft limits and driver bindings"
      />
      <div className="space-y-4 p-6">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Panel className="lg:col-span-1">
            <PanelHeader eyebrow="Platform" title="Soft limits" />
            <dl className="divide-y divide-[var(--color-hairline)] text-sm">
              <Row label="Max voltage" value={`${meta.data?.soft_limits.max_voltage_v ?? "—"} V`} />
              <Row label="Max current" value={`${meta.data?.soft_limits.max_current_a ?? "—"} A`} />
              <Row label="Capability map" value={meta.data?.capability_map_version ?? "—"} mono />
              <Row
                label="Hardware"
                value={meta.data?.hardware_enabled ? "ENABLED" : "disabled (mock)"}
                valueColor={
                  meta.data?.hardware_enabled ? "var(--color-alarm)" : "var(--color-online)"
                }
              />
            </dl>
            <p className="px-4 py-3 text-xs text-[var(--color-ink-faint)]">
              Soft limits are advisory and configurable. Instrument hardware limits
              remain the ultimate authority and are enforced on the device itself.
            </p>
          </Panel>

          <Panel className="lg:col-span-2">
            <PanelHeader eyebrow="Bindings" title="Connection profiles" />
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--color-hairline)] text-left text-xs text-[var(--color-ink-faint)]">
                    <th className="px-4 py-2 font-medium">Unit</th>
                    <th className="px-4 py-2 font-medium">Driver</th>
                    <th className="px-4 py-2 font-medium">Transport</th>
                    <th className="px-4 py-2 font-medium">VISA resource</th>
                    <th className="px-4 py-2 font-medium">Fault profile</th>
                  </tr>
                </thead>
                <tbody>
                  {(devices.data ?? []).map((d) => (
                    <tr key={d.id} className="border-b border-[var(--color-hairline)]/60">
                      <td className="px-4 py-2 text-[var(--color-ink)]">{d.name}</td>
                      <td className="px-4 py-2">
                        <Badge
                          color={
                            d.connection_profile.driver_kind === "mock"
                              ? "var(--color-active)"
                              : "var(--color-warning)"
                          }
                        >
                          {d.connection_profile.driver_kind}
                        </Badge>
                      </td>
                      <td className="px-4 py-2 text-[var(--color-ink-dim)]">
                        {d.connection_profile.connection_type}
                      </td>
                      <td className="readout px-4 py-2 text-[11px] text-[var(--color-ink-faint)]">
                        {d.connection_profile.visa_resource || "—"}
                      </td>
                      <td className="px-4 py-2 text-[var(--color-ink-dim)]">
                        {d.connection_profile.fault_profile}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  mono,
  valueColor,
}: {
  label: string;
  value: string;
  mono?: boolean;
  valueColor?: string;
}) {
  return (
    <div className="flex items-center justify-between px-4 py-2.5">
      <span className="text-xs text-[var(--color-ink-faint)]">{label}</span>
      <span
        className={`${mono ? "readout text-xs" : "text-sm"}`}
        style={{ color: valueColor ?? "var(--color-ink)" }}
      >
        {value}
      </span>
    </div>
  );
}
