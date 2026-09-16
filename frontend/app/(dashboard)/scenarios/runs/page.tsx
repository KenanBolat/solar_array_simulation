"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { usePageHeader } from "@/lib/header-context";
import { useUi } from "@/lib/ui-context";
import { Chip, Panel, RUN_COLOR } from "@/components/ui";

const FILTERS = ["All", "Running", "Completed", "Aborted", "Failed"];
const LVL_COLOR: Record<string, string> = { ok: "#34d399", info: "#8a95a8", warn: "#fbbf24", err: "#f87171" };

export default function ScenarioRunsPage() {
  usePageHeader("Scenario Runs", "Execution history and live run monitor");
  const { ask, notify } = useUi();
  const [filter, setFilter] = useState("All");
  const [selectedId, setSelectedId] = useState("RUN-8842");

  const { data: runs } = usePoll(() => api.runs(filter), 2000, [filter]);
  const { data: run, reload: reloadRun } = usePoll(() => api.run(selectedId), 1500, [selectedId]);

  const activeRun = run ?? (runs ?? [])[0];
  const isLive = activeRun?.status === "Running";

  const onAbort = () => {
    if (!activeRun) return;
    if (!isLive) { notify("Run is not active"); return; }
    ask({
      title: `Abort ${activeRun.id}`,
      message: `Aborting stops the sequence at the current step and runs the scenario's failure action (safe shutdown) on all targets: ${activeRun.targets.join(", ")}.`,
      confirmLabel: "Abort run", danger: true,
      onConfirm: async () => { await api.abortRun(activeRun.id); notify(`Abort dispatched · ${activeRun.id}`); reloadRun(); },
    });
  };

  const onPause = async () => {
    if (!activeRun) return;
    const res = await api.pauseRun(activeRun.id);
    notify(res.message);
  };

  return (
    <div className="p-5">
      <div className="mb-4 flex flex-wrap gap-2">
        {FILTERS.map((f) => <Chip key={f} label={f} active={f === filter} onClick={() => setFilter(f)} />)}
      </div>

      <div className="grid grid-cols-[1fr_380px] items-start gap-4">
        <Panel className="overflow-hidden">
          <div className="grid gap-2.5 border-b border-line px-3.5 py-2 font-mono text-[9px] uppercase tracking-wider text-faint" style={{ gridTemplateColumns: "92px 1fr 52px 84px 110px 78px 76px" }}>
            <span>Run</span><span>Scenario</span><span>Ver</span><span>Status</span><span>Progress</span><span>Started</span><span>By</span>
          </div>
          {(runs ?? []).map((r) => (
            <div key={r.id} onClick={() => setSelectedId(r.id)}
              className="grid cursor-pointer items-center gap-2.5 border-b border-[#161b24] px-3.5 py-2.5"
              style={{
                gridTemplateColumns: "92px 1fr 52px 84px 110px 78px 76px",
                background: r.id === selectedId ? "#2dd4ee0f" : "transparent",
                borderLeft: `2px solid ${r.id === selectedId ? "#2dd4ee" : "transparent"}`,
              }}>
              <span className="font-mono text-[11px] font-bold">{r.id}</span>
              <span className="truncate text-[12px] text-ink">
                {r.scenario}
                {r.dry && <span className="ml-1 font-mono text-[9.5px] text-amber">· dry run</span>}
              </span>
              <span className="font-mono text-[10.5px] text-muted">{r.version}</span>
              <span className="rounded px-1.5 py-0.5 text-center font-mono text-[10px] font-semibold" style={{ color: RUN_COLOR[r.status], border: `1px solid ${RUN_COLOR[r.status]}55` }}>{r.status}</span>
              <span className="block h-[5px] overflow-hidden rounded-full bg-line">
                <span className="block h-full" style={{ width: `${r.prog}%`, background: RUN_COLOR[r.status] }} />
              </span>
              <span className="font-mono text-[10.5px] text-muted">{r.started}</span>
              <span className="font-mono text-[10.5px] text-muted">{r.by}</span>
            </div>
          ))}
        </Panel>

        <div className="flex flex-col gap-3.5">
          {activeRun && (
            <Panel className="p-[15px]">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <div className="mb-0.5 text-[10px] uppercase tracking-wider text-faint">Live monitor</div>
                  <div className="font-mono text-[14px] font-bold">{activeRun.id}</div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className={`h-2 w-2 rounded-full bg-cyan ${isLive ? "animate-scpulse" : ""}`} style={{ boxShadow: "0 0 8px #2dd4ee" }} />
                  <span className="font-mono text-[11px] font-bold" style={{ color: RUN_COLOR[activeRun.status] }}>{activeRun.status}</span>
                </div>
              </div>
              <div className="mb-2.5 text-[12px] text-[#cfd6e2]">{activeRun.scenario} · {activeRun.version}</div>
              <div className="mb-1.5 h-1.5 overflow-hidden rounded-full bg-line">
                <div className="h-full" style={{ width: `${activeRun.prog}%`, background: RUN_COLOR[activeRun.status] }} />
              </div>
              <div className="mb-3.5 flex justify-between font-mono text-[10.5px] text-muted">
                <span>{activeRun.prog}%</span><span>{activeRun.dur}</span>
              </div>
              <div className="flex flex-col gap-2 font-mono text-[11.5px]">
                <div className="flex justify-between"><span className="text-faint">Targets</span><span>{activeRun.targets.join(" · ")}</span></div>
                <div className="flex justify-between"><span className="text-faint">Started</span><span>{activeRun.started}</span></div>
                <div className="flex justify-between"><span className="text-faint">Finished</span><span>{activeRun.finished}</span></div>
                <div className="flex justify-between"><span className="text-faint">Started by</span><span>{activeRun.by}</span></div>
              </div>
              <div className="mt-3.5 flex gap-2">
                <div onClick={onPause} className="cursor-pointer rounded-md border border-line2 bg-panel2 px-3.5 py-1.5 text-[11.5px] font-semibold text-ink">Pause</div>
                <div onClick={onAbort} className="cursor-pointer rounded-md border px-3.5 py-1.5 text-[11.5px] font-semibold"
                  style={{ background: isLive ? "#f871711a" : "transparent", borderColor: isLive ? "#f8717188" : "#2c3543", color: isLive ? "#f87171" : "#5c6678" }}>
                  Abort
                </div>
              </div>
            </Panel>
          )}

          <Panel title="Event timeline" className="overflow-hidden">
            <div className="flex max-h-[340px] flex-col gap-2.5 overflow-y-auto px-3.5 py-2.5">
              {(run?.events ?? []).map((e, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <span className="mt-1.5 h-1.5 w-1.5 flex-none rounded-full" style={{ background: LVL_COLOR[e.lvl], boxShadow: `0 0 6px ${LVL_COLOR[e.lvl]}88` }} />
                  <span className="w-[58px] flex-none font-mono text-[10px] text-faint">{e.t}</span>
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className="self-start rounded border border-line bg-[#0e1117] px-1.5 py-0.5 font-mono text-[9.5px] text-muted">{e.node}</span>
                    <span className="text-[11.5px] leading-snug" style={{ color: e.lvl === "err" ? "#f87171" : e.lvl === "warn" ? "#fbbf24" : "#cfd6e2" }}>{e.m}</span>
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
