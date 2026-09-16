"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { usePageHeader } from "@/lib/header-context";
import { Btn, Chip, Panel, STATUS_COLOR } from "@/components/ui";
import { useUi } from "@/lib/ui-context";

const RANGES = ["5 min", "30 min", "1 hour", "24 hours"];
const Q_COLOR: Record<string, string> = { ok: "#34d399", interp: "#fbbf24", stale: "#f87171" };

export default function MeasurementsPage() {
  usePageHeader("Measurements", "Telemetry explorer · multi-unit comparison");
  const { notify } = useUi();
  const [range, setRange] = useState("30 min");
  const [selected, setSelected] = useState<string[]>([]);
  const defaultedRef = useRef(false);

  const { data: units } = usePoll(() => api.units(), 8000);
  const { data: meas } = usePoll(() => api.measurements(selected, range), 4000, [selected.join(","), range]);

  // Pick a sensible default selection the first time real units arrive.
  useEffect(() => {
    if (!defaultedRef.current && units && units.length > 0) {
      defaultedRef.current = true;
      setSelected(units.filter((u) => u.online).slice(0, 5).map((u) => u.name));
    }
  }, [units]);

  const online = (units ?? []).filter((u) => u.online).slice(0, 10);

  const toggle = (name: string) =>
    setSelected((s) => (s.includes(name) ? s.filter((x) => x !== name) : [...s, name]));

  return (
    <div className="p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-1.5 text-[10px] uppercase tracking-wider text-faint">Units compared</div>
          <div className="flex flex-wrap gap-1.5">
            {online.map((u) => {
              const active = selected.includes(u.name);
              const c = STATUS_COLOR[u.statusColor];
              return (
                <div key={u.name} onClick={() => toggle(u.name)}
                  className="cursor-pointer rounded-md px-2.5 py-1 font-mono text-[11px] font-semibold"
                  style={{ color: active ? "#04121a" : "#8a95a8", background: active ? c : "transparent", border: `1px solid ${active ? c : "#232a36"}` }}>
                  {u.name}
                </div>
              );
            })}
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
          <div className="mb-1.5 text-[13px] font-semibold text-[#cfd6e2]">No units selected</div>
          <div className="text-[12px] text-muted">Pick one or more units above to plot their telemetry.</div>
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
                        const min = Math.min(...values, 0), max = Math.max(...values, 1);
                        const pad = (max - min) * 0.1 || 1;
                        const points = values.map((v, idx) => {
                          const x = (idx / Math.max(1, values.length - 1)) * 560;
                          const y = 80 - ((v - (min - pad)) / (max - min + pad * 2 || 1)) * 80;
                          return `${x.toFixed(1)},${Math.max(2, Math.min(78, y)).toFixed(1)}`;
                        }).join(" ");
                        return <polyline key={s.name} points={points} fill="none" stroke={STATUS_COLOR[s.statusColor]} strokeWidth={1.6} />;
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
              <span>Unit</span><span>Time</span><span>Voltage</span><span>Current</span><span>Power</span><span>Out</span><span>Quality</span>
            </div>
            {(meas?.rows ?? []).map((m, idx) => {
              const u = (units ?? []).find((x) => x.name === m.unit);
              return (
                <div key={idx} className="grid items-center gap-2.5 border-b border-[#161b24] px-3.5 py-2 font-mono text-[11px]" style={{ gridTemplateColumns: "76px 66px 1fr 1fr 1fr 52px 66px" }}>
                  <span className="font-bold" style={{ color: u ? STATUS_COLOR[u.statusColor] : "#e6eaf2" }}>{m.unit}</span>
                  <span className="text-muted">{m.time}</span>
                  <span>{m.v.toFixed(3)}<span className="text-faint"> V</span></span>
                  <span>{m.i.toFixed(3)}<span className="text-faint"> A</span></span>
                  <span>{m.p.toFixed(2)}<span className="text-faint"> W</span></span>
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
            <div className="flex justify-between"><span className="text-faint">Poll interval</span><span>500 ms</span></div>
            <div className="flex justify-between"><span className="text-faint">Raw retention</span><span>7 days</span></div>
            <div className="flex justify-between"><span className="text-faint">Downsampled</span><span>1 year @ 1 min</span></div>
            <div className="flex justify-between"><span className="text-faint">Units plotted</span><span>{meas?.count ?? 0}</span></div>
          </div>
          <div className="my-3.5 h-px bg-line" />
          <div className="mb-2 text-[10px] uppercase tracking-wider text-faint">Quality flags</div>
          <div className="flex flex-col gap-1.5 text-[11px] text-[#cfd6e2]">
            <div className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-green" />ok — sampled from device</div>
            <div className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-amber" />interp — gap filled</div>
            <div className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-red" />stale — poll missed</div>
          </div>
        </Panel>
      </div>
    </div>
  );
}
