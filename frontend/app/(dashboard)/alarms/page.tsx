"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { usePageHeader } from "@/lib/header-context";
import { useUi } from "@/lib/ui-context";
import { Chip, SEV_COLOR } from "@/components/ui";

const FILTERS = ["Active", "History", "All"];

export default function AlarmsPage() {
  usePageHeader("Alarms", "Active conditions and alarm history");
  const { notify } = useUi();
  const [filter, setFilter] = useState("Active");
  const { data, reload } = usePoll(() => api.alarms(filter), 3000, [filter]);

  return (
    <div className="p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => <Chip key={f} label={f} active={f === filter} onClick={() => setFilter(f)} />)}
        </div>
        <div className="flex gap-2.5">
          <div className="flex items-center gap-1.5 rounded-md border border-amber/30 bg-amber/10 px-2.5 py-1.5">
            <span className="font-mono text-[11px] font-semibold text-amber">{data?.activeCount ?? 0} ACTIVE</span>
          </div>
          <div className="flex items-center gap-1.5 rounded-md border border-red/30 bg-red/10 px-2.5 py-1.5">
            <span className="font-mono text-[11px] font-semibold text-red">{data?.critCount ?? 0} CRITICAL</span>
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-2.5">
        {(data?.rows ?? []).map((a) => {
          const c = SEV_COLOR[a.sev];
          return (
            <div key={a.id} className="relative overflow-hidden rounded-[9px] border border-line bg-panel py-3.5 pl-4.5 pr-4">
              <div className="absolute inset-y-0 left-0 w-[3px]" style={{ background: c }} />
              <div className="flex items-start justify-between gap-3.5">
                <div className="min-w-0 flex-1">
                  <div className="mb-1.5 flex flex-wrap items-center gap-2.5">
                    <span className="rounded font-mono text-[9.5px] font-semibold tracking-wider" style={{ color: c, border: `1px solid ${c}55`, padding: "2px 6px" }}>
                      {a.sev.toUpperCase()}
                    </span>
                    <span className="font-mono text-[12.5px] font-bold">{a.unit}</span>
                    <span className="font-mono text-[10.5px] text-muted">{a.code}</span>
                    <span className="font-mono text-[10.5px] text-faint">{a.time}</span>
                  </div>
                  <div className="text-[12.5px] leading-relaxed text-[#cfd6e2]">{a.msg}</div>
                </div>
                <div className="flex flex-none items-center gap-2.5">
                  {a.ackd && <span className="text-[11px] font-semibold text-green">✓ Acknowledged</span>}
                  {!a.ackd && (
                    <button onClick={async () => { await api.ackAlarm(a.id); notify(`Acknowledged · ${a.unit} · ${a.code}`); reload(); }}
                      className="rounded-md border border-line2 bg-panel2 px-3 py-1.5 text-[11px] font-semibold text-ink">
                      Acknowledge
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
        {(data?.rows ?? []).length === 0 && (
          <div className="rounded-[10px] border border-dashed border-line2 bg-panel p-12 text-center text-[12px] text-muted">
            No alarms in this view.
          </div>
        )}
      </div>
    </div>
  );
}
