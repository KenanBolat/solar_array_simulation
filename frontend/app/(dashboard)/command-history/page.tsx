"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { usePageHeader } from "@/lib/header-context";
import { useUi } from "@/lib/ui-context";
import { Btn, Chip, HIST_COLOR, Panel } from "@/components/ui";

const FILTERS = ["All", "OK", "WARN", "ERR"];

export default function CommandHistoryPage() {
  usePageHeader("Command History", "Traceability and audit log");
  const { notify } = useUi();
  const [filter, setFilter] = useState("All");
  const { data } = usePoll(() => api.history(filter, 200), 4000, [filter]);

  return (
    <div className="p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap gap-2">
          {FILTERS.map((f) => <Chip key={f} label={f} active={f === filter} onClick={() => setFilter(f)} />)}
        </div>
        <div className="flex items-center gap-3">
          <span className="font-mono text-[11px] text-faint">{data?.shown ?? 0} of {data?.total ?? 0} records</span>
          <Btn variant="primary" onClick={() => notify(`Audit export queued · ${data?.shown ?? 0} records`)}>Export audit log</Btn>
        </div>
      </div>

      <Panel className="overflow-hidden">
        <div className="grid gap-2.5 border-b border-line px-3.5 py-2 font-mono text-[9px] uppercase tracking-wider text-faint"
          style={{ gridTemplateColumns: "76px 74px 76px 1fr 62px 78px 44px 82px" }}>
          <span>Time</span><span>Actor</span><span>Device</span><span>Template</span><span>Status</span><span>Latency</span><span>RB</span><span>Correlation</span>
        </div>
        {(data?.rows ?? []).map((h) => (
          <div key={h.cid} onClick={() => notify(`Correlation ${h.cid} · ${h.tpl} · ${h.dev}`)}
            className="grid cursor-pointer items-center gap-2.5 border-b border-[#161b24] px-3.5 py-2.5 font-mono text-[11px]"
            style={{ gridTemplateColumns: "76px 74px 76px 1fr 62px 78px 44px 82px" }}>
            <span className="text-muted">{h.t}</span>
            <span className="text-[#cfd6e2]">{h.user}</span>
            <span className="font-semibold">{h.dev}</span>
            <span className="truncate text-ink">{h.tpl}</span>
            <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold" style={{ color: HIST_COLOR[h.st], border: `1px solid ${HIST_COLOR[h.st]}55` }}>{h.st}</span>
            <span className="text-muted">{h.lat}</span>
            <span style={{ color: h.rb ? "#34d399" : "#5c6678" }}>{h.rb ? "✓" : "✗"}</span>
            <span className="text-faint">{h.cid}</span>
          </div>
        ))}
        <div className="px-3.5 py-3 text-[11px] leading-relaxed text-faint">
          Every command dispatched from any surface — software controls, front panel, terminal or scenario run — is recorded here with its actor, correlation id and readback result. Records are append-only.
        </div>
      </Panel>
    </div>
  );
}
