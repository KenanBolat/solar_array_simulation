"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { usePageHeader } from "@/lib/header-context";
import { useUi } from "@/lib/ui-context";
import { Btn, Chip, HIST_COLOR, Panel } from "@/components/ui";

const FILTERS = ["All", "OK", "ERR", "UNREACHABLE", "TIMEOUT"];
const GRID = "70px 60px 64px 150px 1.6fr 96px 66px 36px 84px";

export default function CommandHistoryPage() {
  usePageHeader("Command History", "Traceability and audit log");
  const { notify } = useUi();
  const [filter, setFilter] = useState("All");
  const [open, setOpen] = useState<string | null>(null);
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
          style={{ gridTemplateColumns: GRID }}>
          <span>Time</span><span>Actor</span><span>Device</span><span>Template</span><span>SCPI sent</span><span>Status</span><span>Latency</span><span>RB</span><span>Correlation</span>
        </div>
        {(data?.rows ?? []).map((h) => {
          const color = HIST_COLOR[h.st] ?? "#8a95a8";
          const expanded = open === h.cid;
          return (
            <div key={h.cid} className="border-b border-[#161b24]">
              <div onClick={() => setOpen(expanded ? null : h.cid)}
                className="grid cursor-pointer items-center gap-2.5 px-3.5 py-2.5 font-mono text-[11px] hover:bg-panel2/40"
                style={{ gridTemplateColumns: GRID }}>
                <span className="text-muted">{h.t}</span>
                <span className="text-[#cfd6e2]">{h.user}</span>
                <span className="font-semibold">{h.dev}</span>
                <span className="truncate text-ink">{h.tpl}</span>
                <span className="truncate text-cyan" title={h.scpi}>{h.scpi || "—"}</span>
                <span className="truncate rounded px-1.5 py-0.5 text-center text-[10px] font-semibold" style={{ color, border: `1px solid ${color}55` }}>{h.st}</span>
                <span className="text-muted">{h.lat}</span>
                <span title={h.rb ? "readback confirmed the commanded value" : "no readback / mismatch"} style={{ color: h.rb ? "#34d399" : "#5c6678" }}>{h.rb ? "✓" : "✗"}</span>
                <span className="text-faint">{h.cid}</span>
              </div>
              {expanded && (
                <div className="grid gap-x-6 gap-y-1 bg-bg/60 px-3.5 pb-3 pt-1 font-mono text-[11px]" style={{ gridTemplateColumns: "90px 1fr" }}>
                  <span className="text-faint">sent</span><span className="break-all text-cyan">{h.scpi || "—"}</span>
                  <span className="text-faint">response</span><span className="break-all text-ink">{h.resp || "—"}</span>
                  <span className="text-faint">outcome</span>
                  <span style={{ color }}>
                    {h.st === "OK" && `accepted · SYST:ERR? +0,"No error"${h.rb ? " · readback verified" : ""}`}
                    {h.st === "ERR" && `rejected by instrument · SYST:ERR? ${h.errCode},"${h.err}"`}
                    {(h.st === "UNREACHABLE" || h.st === "TIMEOUT") && `${h.st.toLowerCase()} · ${h.err || "no reply"} — command never took effect`}
                  </span>
                </div>
              )}
            </div>
          );
        })}
        <div className="px-3.5 py-3 text-[11px] leading-relaxed text-faint">
          Every command dispatched from any surface — software controls, front panel, terminal or scenario run — is recorded here with the exact SCPI
          program message, the instrument&apos;s readback, its <span className="font-mono">SYST:ERR?</span> verdict and the transport outcome. Click a row for detail. Records are append-only.
        </div>
      </Panel>
    </div>
  );
}
