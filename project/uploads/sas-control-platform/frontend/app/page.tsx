"use client";

import Link from "next/link";
import { useMemo } from "react";
import { ArrowRight, CircuitBoard } from "lucide-react";
import { PageHeader, StatCard } from "@/components/PageHeader";
import { Panel, PanelHeader, Badge } from "@/components/ui/primitives";
import { RackVisual } from "@/components/RackVisual";
import { useAlarms, useAuditLog, useDevices, useRacks } from "@/lib/hooks";
import { fmt, relTime } from "@/lib/utils";
import type { Device } from "@/lib/types";

export default function DashboardPage() {
  const racks = useRacks();
  const devices = useDevices();
  const alarms = useAlarms(true);
  const audit = useAuditLog(8);

  const stats = useMemo(() => {
    const list = devices.data ?? [];
    let online = 0;
    let outputs = 0;
    let power = 0;
    let faults = 0;
    for (const d of list) {
      const s = d.last_state || {};
      if (s.device_state && s.device_state !== "offline") online += 1;
      if (s.output_enabled) outputs += 1;
      power += s.power_w ?? 0;
      if (s.device_state === "alarm" || s.device_state === "warning") faults += 1;
    }
    return { total: list.length, online, outputs, power, faults };
  }, [devices.data]);

  const byRack = useMemo(() => {
    const map = new Map<string, Device[]>();
    for (const d of devices.data ?? []) {
      const arr = map.get(d.rack_id) ?? [];
      arr.push(d);
      map.set(d.rack_id, arr);
    }
    return map;
  }, [devices.data]);

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="Fleet status across all racks and simulator units"
      />

      <div className="space-y-6 p-6">
        {/* KPI row */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <StatCard label="Units" value={stats.total} accent="var(--color-ink)" />
          <StatCard
            label="Online"
            value={stats.online}
            accent="var(--color-online)"
          />
          <StatCard
            label="Outputs Enabled"
            value={stats.outputs}
            accent="var(--color-output)"
          />
          <StatCard
            label="Total Power"
            value={fmt(stats.power, 0)}
            unit="W"
            accent="var(--color-scenario)"
          />
          <StatCard
            label="Faults"
            value={stats.faults}
            accent={stats.faults > 0 ? "var(--color-alarm)" : "var(--color-ink)"}
          />
        </div>

        {/* Racks */}
        <div>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-[var(--color-ink)]">
              <CircuitBoard size={15} style={{ color: "var(--color-active)" }} />
              Racks
            </h2>
            <Link
              href="/racks"
              className="flex items-center gap-1 text-xs text-[var(--color-ink-dim)] hover:text-[var(--color-active)]"
            >
              Rack explorer <ArrowRight size={12} />
            </Link>
          </div>
          {racks.isLoading || devices.isLoading ? (
            <LoadingGrid />
          ) : (
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
              {(racks.data ?? [])
                .slice()
                .sort((a, b) => a.position - b.position)
                .map((r) => (
                  <RackVisual
                    key={r.id}
                    name={r.name}
                    location={r.location}
                    devices={(byRack.get(r.id) ?? []).slice().sort((a, b) =>
                      a.name.localeCompare(b.name)
                    )}
                  />
                ))}
            </div>
          )}
        </div>

        {/* Recent commands + active alarms */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Panel>
            <PanelHeader
              eyebrow="Audit"
              title="Recent commands"
              actions={
                <Link
                  href="/command-history"
                  className="text-xs text-[var(--color-ink-dim)] hover:text-[var(--color-active)]"
                >
                  All
                </Link>
              }
            />
            <div className="divide-y divide-[var(--color-hairline)]">
              {(audit.data ?? []).length === 0 ? (
                <Empty>No commands issued yet.</Empty>
              ) : (
                (audit.data ?? []).map((a) => (
                  <div key={a.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                    <OutcomeDot outcome={a.outcome} />
                    <span className="readout text-xs text-[var(--color-ink)]">
                      {a.action.replace("command:", "")}
                    </span>
                    <span className="text-xs text-[var(--color-ink-faint)]">{a.actor}</span>
                    <span className="ml-auto text-xs text-[var(--color-ink-faint)]">
                      {relTime(a.ts_utc)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </Panel>

          <Panel>
            <PanelHeader
              eyebrow="Safety"
              title="Active alarms"
              actions={
                <Link
                  href="/alarms"
                  className="text-xs text-[var(--color-ink-dim)] hover:text-[var(--color-active)]"
                >
                  All
                </Link>
              }
            />
            <div className="divide-y divide-[var(--color-hairline)]">
              {(alarms.data ?? []).length === 0 ? (
                <Empty>No active alarms. All units within limits.</Empty>
              ) : (
                (alarms.data ?? []).map((al) => (
                  <div key={al.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                    <Badge
                      color={
                        al.severity === "alarm" || al.severity === "critical"
                          ? "var(--color-alarm)"
                          : "var(--color-warning)"
                      }
                    >
                      {al.severity}
                    </Badge>
                    <span className="readout text-xs">{al.code}</span>
                    <span className="truncate text-xs text-[var(--color-ink-dim)]">
                      {al.message}
                    </span>
                    <span className="ml-auto text-xs text-[var(--color-ink-faint)]">
                      {relTime(al.ts_utc)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}

function OutcomeDot({ outcome }: { outcome: string }) {
  const ok = outcome === "completed";
  const color = ok
    ? "var(--color-output)"
    : outcome === "rejected" || outcome === "failed" || outcome === "timed_out"
      ? "var(--color-alarm)"
      : "var(--color-warning)";
  return <span className="status-dot" style={{ color, background: color }} />;
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="px-4 py-8 text-center text-sm text-[var(--color-ink-faint)]">{children}</div>;
}

function LoadingGrid() {
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      {[0, 1, 2].map((i) => (
        <div key={i} className="panel h-64 animate-pulse opacity-50" />
      ))}
    </div>
  );
}
