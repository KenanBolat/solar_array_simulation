"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { usePageHeader } from "@/lib/header-context";
import { Btn, Chip, Panel, STATUS_COLOR } from "@/components/ui";
import { useUi } from "@/lib/ui-context";

const RANGES = ["5 min", "30 min", "1 hour", "24 hours"];
const Q_COLOR: Record<string, string> = { ok: "#34d399", no_reading: "#f87171" };

function seriesToSegments(values: (number | null)[], lo: number, hi: number, w: number, h: number): string[] {
  const segments: string[][] = [[]];
  values.forEach((v, idx) => {
    if (v == null) {
      if (segments[segments.length - 1].length) segments.push([]);
      return;
    }
    const x = (idx / Math.max(1, values.length - 1)) * w;
    const y = h - ((v - lo) / (hi - lo || 1)) * h;
    segments[segments.length - 1].push(`${x.toFixed(1)},${Math.max(2, Math.min(h - 2, y)).toFixed(1)}`);
  });
  return segments.filter((s) => s.length).map((s) => s.join(" "));
}

export default function MeasurementsPage() {
  usePageHeader("Measurements", "Telemetry explorer · every channel of every mainframe");
  const { notify } = useUi();
  const [range, setRange] = useState("30 min");
  const [selected, setSelected] = useState<string[]>([]);
  const defaultedRef = useRef(false);

  const { data: units } = usePoll(() => api.units(), 8000);
  const { data: meas } = usePoll(() => api.measurements(selected, range), 4000, [selected.join(","), range]);

  // Every channel of every configured mainframe is plotted by default — an
  // E4360 holds two output modules, and both are units here.
  useEffect(() => {
    if (!defaultedRef.current && units && units.length > 0) {
      defaultedRef.current = true;
      setSelected(units.filter((u) => u.enabled).map((u) => u.name));
    }
  }, [units]);

  // Enabled units stay pickable even while their comms link is down, so you
  // can still pull up their history from before/after the outage — only
  // fully-removed (disabled) units drop off the list.
  const pickable = (units ?? []).filter((u) => u.enabled);

  // Group the chips by mainframe so two channels of one instrument read as
  // one instrument, not two unrelated devices.
  const byMainframe = pickable.reduce<Record<string, typeof pickable>>((acc, u) => {
    (acc[u.mainframe || "unaddressed"] ||= []).push(u);
    return acc;
  }, {});
  Object.values(byMainframe).forEach((list) => list.sort((a, b) => a.channel - b.channel));

  const toggle = (name: string) =>
    setSelected((s) => (s.includes(name) ? s.filter((x) => x !== name) : [...s, name]));
  const allSelected = pickable.length > 0 && pickable.every((u) => selected.includes(u.name));

  return (
    <div className="p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-1.5 flex items-center gap-2.5">
            <span className="text-[10px] uppercase tracking-wider text-faint">Channels compared</span>
            <button onClick={() => setSelected(allSelected ? [] : pickable.map((u) => u.name))}
              className="rounded border border-line2 bg-panel2 px-1.5 py-0.5 text-[9.5px] font-semibold text-muted">
              {allSelected ? "Clear all" : "Select all"}
            </button>
          </div>
          <div className="flex flex-wrap items-start gap-3">
            {Object.entries(byMainframe).map(([mf, list]) => (
              <div key={mf} className="rounded-md border border-line bg-panel px-2 py-1.5">
                <div className="mb-1 font-mono text-[9px] text-faint">{mf}</div>
                <div className="flex flex-wrap gap-1.5">
                  {list.map((u) => {
                    const active = selected.includes(u.name);
                    const c = STATUS_COLOR[u.statusColor];
                    return (
                      <div key={u.name} onClick={() => toggle(u.name)} title={u.online ? `${u.name} · channel ${u.channel}` : "Comms currently down"}
                        className="cursor-pointer rounded-md px-2.5 py-1 font-mono text-[11px] font-semibold"
                        style={{
                          color: active ? "#04121a" : u.online ? "#8a95a8" : "#f87171",
                          background: active ? c : "transparent",
                          border: `1px solid ${active ? c : u.online ? "#232a36" : "#f8717155"}`,
                        }}>
                        {u.name} <span style={{ opacity: 0.7 }}>(@{u.channel})</span>{!u.online && !active && " ⚠"}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="flex items-end gap-2">
          <div>
            <div className="mb-1.5 text-[10px] uppercase tracking-wider text-faint">Range</div>
            <div className="flex gap-1.5">
              {RANGES.map((r) => <Chip key={r} label={r} active={r === range} onClick={() => setRange(r)} />)}
            </div>
          </div>
          <Btn variant="primary" onClick={() => notify(`Export queued · ${selected.length} units · ${range}`)}>Export CSV</Btn>
        </div>
      </div>

      {selected.length === 0 && (
        <div className="mb-4 rounded-[10px] border border-dashed border-line2 bg-panel p-12 text-center">
          <div className="mb-1.5 text-[13px] font-semibold text-[#cfd6e2]">No channels selected</div>
          <div className="text-[12px] text-muted">Pick one or more channels above to plot their telemetry.</div>
        </div>
      )}

      <div className="grid grid-cols-[1fr_340px] items-start gap-4">
        <div className="flex flex-col gap-3.5">
          <Panel className="p-3.5">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-[12px] font-semibold">Voltage · Current · Power</div>
              <div className="flex gap-3">
                {(meas?.series ?? []).map((s) => (
                  <div key={s.name} className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-sm" style={{ background: STATUS_COLOR[s.statusColor] }} />
                    <span className="font-mono text-[10.5px] text-muted">{s.name}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="flex flex-col gap-2.5">
              {(["v", "i", "p"] as const).map((k) => (
                <div key={k}>
                  <div className="mb-1 font-mono text-[9.5px] text-faint">{k === "v" ? "VOLTAGE · V" : k === "i" ? "CURRENT · A" : "POWER · W"}</div>
                  <div className="relative">
                    <svg viewBox="0 0 560 80" preserveAspectRatio="none" className="h-[84px] w-full rounded-md border border-line bg-[#0e1117]">
                      {(meas?.series ?? []).map((s) => {
                        const values = s[k];
                        const real = values.filter((v): v is number => v != null);
                        const min = Math.min(...real, 0), max = Math.max(...real, 1);
                        const pad = (max - min) * 0.1 || 1;
                        const segments = seriesToSegments(values, min - pad, max + pad, 560, 80);
                        return segments.map((points, idx) => (
                          <polyline key={`${s.name}-${idx}`} points={points} fill="none" stroke={STATUS_COLOR[s.statusColor]} strokeWidth={1.6} />
                        ));
                      })}
                    </svg>
                  </div>
                </div>
              ))}
            </div>
          </Panel>

          <Panel className="overflow-hidden">
            <div className="flex items-center justify-between border-b border-line px-3.5 py-2.5">
              <div className="text-[12px] font-semibold">Recent samples</div>
              <span className="font-mono text-[10.5px] text-faint">{meas?.sampleText}</span>
            </div>
            <div className="grid gap-2.5 border-b border-line px-3.5 py-2 font-mono text-[9px] uppercase tracking-wider text-faint" style={{ gridTemplateColumns: "76px 66px 1fr 1fr 1fr 52px 66px" }}>
              <span>Channel</span><span>Time</span><span>Voltage</span><span>Current</span><span>Power</span><span>Out</span><span>Quality</span>
            </div>
            {(meas?.rows ?? []).map((m, idx) => {
              const u = (units ?? []).find((x) => x.name === m.unit);
              return (
                <div key={idx} className="grid items-center gap-2.5 border-b border-[#161b24] px-3.5 py-2 font-mono text-[11px]" style={{ gridTemplateColumns: "76px 66px 1fr 1fr 1fr 52px 66px" }}>
                  <span className="font-bold" style={{ color: u ? STATUS_COLOR[u.statusColor] : "#e6eaf2" }}
                    title={u ? `${u.mainframe} (@${u.channel})` : undefined}>{m.unit}</span>
                  <span className="text-muted">{m.time}</span>
                  <span>{m.v != null ? <>{m.v.toFixed(3)}<span className="text-faint"> V</span></> : <span className="text-faint">—</span>}</span>
                  <span>{m.i != null ? <>{m.i.toFixed(3)}<span className="text-faint"> A</span></> : <span className="text-faint">—</span>}</span>
                  <span>{m.p != null ? <>{m.p.toFixed(2)}<span className="text-faint"> W</span></> : <span className="text-faint">—</span>}</span>
                  <span className="text-muted">{m.out}</span>
                  <span>
                    <span className="rounded px-1.5 py-0.5 text-[9.5px] font-semibold" style={{ color: Q_COLOR[m.q], border: `1px solid ${Q_COLOR[m.q]}55` }}>{m.q}</span>
                  </span>
                </div>
              );
            })}
          </Panel>
        </div>

        <Panel className="p-3.5">
          <div className="mb-2.5 text-[11px] uppercase tracking-wider text-muted">Retention &amp; quality</div>
          <div className="flex flex-col gap-2 font-mono text-[11.5px]">
            <div className="flex justify-between"><span className="text-faint">Poll interval</span><span>1 s</span></div>
            <div className="flex justify-between"><span className="text-faint">Raw retention</span><span>7 days</span></div>
            <div className="flex justify-between"><span className="text-faint">Downsampled</span><span>1 year @ 1 min</span></div>
            <div className="flex justify-between"><span className="text-faint">Channels plotted</span><span>{meas?.count ?? 0}</span></div>
            <div className="flex justify-between"><span className="text-faint">Mainframes</span><span>{Object.keys(byMainframe).length}</span></div>
          </div>
          <div className="my-3.5 h-px bg-line" />
          <div className="mb-2 text-[10px] uppercase tracking-wider text-faint">Quality flags</div>
          <div className="flex flex-col gap-1.5 text-[11px] text-[#cfd6e2]">
            <div className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-green" />ok — real reading from the unit</div>
            <div className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-red" />no_reading — comms down when polled, stored as null</div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
