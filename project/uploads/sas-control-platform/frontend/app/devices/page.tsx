"use client";

import Link from "next/link";
import { useState } from "react";
import { Search } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { StatusDot } from "@/components/ui/primitives";
import { useDevices } from "@/lib/hooks";
import { fmt, stateColor, stateLabel } from "@/lib/utils";

export default function DevicesIndexPage() {
  const devices = useDevices();
  const [q, setQ] = useState("");
  const list = (devices.data ?? []).filter((d) =>
    d.name.toLowerCase().includes(q.toLowerCase())
  );

  return (
    <div>
      <PageHeader
        title="Simulator Control"
        subtitle="Select a unit to open its control console"
      />
      <div className="p-6">
        <div className="mb-4 flex items-center gap-2 rounded-md border border-[var(--color-hairline)] bg-[var(--color-surface)] px-3 py-2 lg:w-80">
          <Search size={15} className="text-[var(--color-ink-faint)]" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter units…"
            className="w-full bg-transparent text-sm text-[var(--color-ink)] outline-none placeholder:text-[var(--color-ink-faint)]"
          />
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {list.map((d) => {
            const s = d.last_state || {};
            const color = stateColor(s.device_state);
            return (
              <Link
                key={d.id}
                href={`/devices/${d.id}`}
                className="panel group px-4 py-3 transition-colors hover:border-[var(--color-hairline-strong)]"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-[var(--color-ink)]">{d.name}</span>
                  <StatusDot color={color} pulse={s.device_state === "alarm"} />
                </div>
                <div className="mt-0.5 text-[11px] text-[var(--color-ink-faint)]">
                  {stateLabel(s.device_state)} · {d.connection_profile.driver_kind}
                </div>
                <div className="readout mt-3 grid grid-cols-3 gap-2 text-xs">
                  <Cell label="V" value={fmt(s.voltage_v, 1)} />
                  <Cell label="A" value={fmt(s.current_a, 2)} />
                  <Cell label="W" value={fmt(s.power_w, 0)} />
                </div>
              </Link>
            );
          })}
        </div>
        {list.length === 0 ? (
          <p className="py-12 text-center text-sm text-[var(--color-ink-faint)]">
            No units match “{q}”.
          </p>
        ) : null}
      </div>
    </div>
  );
}

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[var(--color-hairline)] bg-[var(--color-base)] px-2 py-1.5">
      <div className="text-[9px] text-[var(--color-ink-faint)]">{label}</div>
      <div className="text-[var(--color-ink)]">{value}</div>
    </div>
  );
}
