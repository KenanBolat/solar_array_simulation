"use client";

import { Check, Minus, ShieldCheck } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Panel, PanelHeader, Badge } from "@/components/ui/kit";
import { useMeta, useRole } from "@/lib/hooks";

const PERMISSIONS = ["view", "run_scenario", "control_output", "approve_scenario", "admin"];
const ROLE_PERMISSIONS: Record<string, string[]> = {
  observer: ["view"],
  operator: ["view", "run_scenario", "control_output"],
  supervisor: ["view", "run_scenario", "control_output", "approve_scenario"],
  administrator: ["view", "run_scenario", "control_output", "approve_scenario", "admin"],
};

export default function AdminPage() {
  const role = useRole();
  const meta = useMeta();

  if (role !== "administrator") {
    return (
      <div>
        <PageHeader title="Administration" subtitle="Restricted area" />
        <div className="flex flex-col items-center justify-center gap-3 p-16 text-center">
          <ShieldCheck size={28} className="text-[var(--color-ink-faint)]" />
          <p className="text-sm text-[var(--color-ink-dim)]">
            Administration is restricted to the administrator role.
          </p>
          <p className="text-xs text-[var(--color-ink-faint)]">
            Switch the acting role in the sidebar (development) to view this page.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title="Administration" subtitle="Roles, permissions and platform settings" />
      <div className="grid grid-cols-1 gap-4 p-6 lg:grid-cols-3">
        <Panel className="lg:col-span-2">
          <PanelHeader eyebrow="RBAC" title="Roles & permissions" />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-hairline)] text-left text-xs text-[var(--color-ink-faint)]">
                  <th className="px-4 py-2 font-medium">Role</th>
                  {PERMISSIONS.map((p) => (
                    <th key={p} className="px-3 py-2 text-center font-medium">
                      {p}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(ROLE_PERMISSIONS).map(([r, perms]) => (
                  <tr key={r} className="border-b border-[var(--color-hairline)]/60">
                    <td className="px-4 py-2.5 font-medium text-[var(--color-ink)]">{r}</td>
                    {PERMISSIONS.map((p) => (
                      <td key={p} className="px-3 py-2.5 text-center">
                        {perms.includes(p) ? (
                          <Check size={14} className="mx-auto" style={{ color: "var(--color-output)" }} />
                        ) : (
                          <Minus size={14} className="mx-auto text-[var(--color-ink-faint)]" />
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="px-4 py-3 text-xs text-[var(--color-ink-faint)]">
            In production these map to directory groups (SSO/JWT). The dev-auth role
            selector impersonates a seeded user via the X-Dev-User header.
          </p>
        </Panel>

        <Panel>
          <PanelHeader eyebrow="Platform" title="System" />
          <dl className="divide-y divide-[var(--color-hairline)] text-sm">
            <Row label="Application" value={meta.data?.app_name ?? "—"} />
            <Row label="Capability map" value={meta.data?.capability_map_version ?? "—"} mono />
            <Row label="Simulation mode" value={meta.data?.simulation_mode ? "on" : "off"} />
            <Row
              label="Hardware"
              value={meta.data?.hardware_enabled ? "ENABLED" : "disabled"}
              valueColor={meta.data?.hardware_enabled ? "var(--color-alarm)" : "var(--color-online)"}
            />
          </dl>
          <div className="px-4 py-3">
            <div className="eyebrow mb-2">Data retention</div>
            <div className="flex flex-wrap gap-2">
              <Badge color="var(--color-active)">measurements: hypertable</Badge>
              <Badge color="var(--color-offline)">1-min rollup</Badge>
              <Badge color="var(--color-offline)">configurable policy</Badge>
            </div>
            <p className="mt-2 text-xs text-[var(--color-ink-faint)]">
              Raw telemetry is stored in a TimescaleDB hypertable with a continuous
              1-minute aggregate and a configurable retention policy.
            </p>
          </div>
        </Panel>
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
      <span className={mono ? "readout text-xs" : "text-sm"} style={{ color: valueColor ?? "var(--color-ink)" }}>
        {value}
      </span>
    </div>
  );
}
