"use client";
import Link from "next/link";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { usePageHeader } from "@/lib/header-context";
import { STATUS_COLOR, SEV_COLOR, RUN_COLOR, StatCard } from "@/components/ui";
import type { Unit } from "@/lib/types";

function UnitCard({ u }: { u: Unit }) {
  const c = STATUS_COLOR[u.statusColor];
  return (
    <Link
      href={`/control/${u.name}`}
      className="relative block overflow-hidden rounded-[7px] border border-line bg-[#161b24] py-2.5 pl-3.5 pr-2.5"
    >
      <div className="absolute inset-y-0 left-0 w-[3px]" style={{ background: c }} />
      <div className="mb-1.5 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="h-[9px] w-[9px] rounded-full" style={{ background: c, boxShadow: `0 0 8px ${c}66` }} />
          <span className="font-mono text-[12.5px] font-bold">{u.name}</span>
        </div>
        <span
          className="rounded font-mono text-[10px] font-semibold"
          style={{
            color: !u.online ? "#5c6678" : u.output ? "#2dd4ee" : "#8a95a8",
            background: !u.online ? "#ffffff08" : u.output ? "#2dd4ee18" : "#ffffff0a",
            padding: "2px 6px",
          }}
        >
          {!u.online ? "—" : u.output ? "ON" : "OFF"}
        </span>
      </div>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="font-mono text-[9.5px] text-faint">{u.pos}</span>
        <span
          className="rounded font-mono text-[10px] font-semibold tracking-wider"
          style={{ color: c, border: `1px solid ${c}55`, background: `${c}14`, padding: "2px 6px" }}
        >
          {u.statusText}
        </span>
      </div>
      <div className="flex gap-2.5 font-mono">
        <div className="flex-1">
          <div className="text-[9px] text-faint">V</div>
          <div className="text-[12px] font-semibold">{u.online ? u.voltage.toFixed(1) : "—"}</div>
        </div>
        <div className="flex-1">
          <div className="text-[9px] text-faint">A</div>
          <div className="text-[12px] font-semibold">{u.online ? u.current.toFixed(1) : "—"}</div>
        </div>
        <div className="flex-1">
          <div className="text-[9px] text-faint">W</div>
          <div className="text-[12px] font-semibold">{u.online ? u.power.toFixed(1) : "—"}</div>
        </div>
      </div>
    </Link>
  );
}

export default function OverviewPage() {
  usePageHeader("Rack Overview", "Physical layout · 3 racks · 20 units");
  const { data: summary } = usePoll(() => api.summary(), 4000);
  const { data: racks } = usePoll(() => api.racks(), 4000);
  const { data: alarmsData } = usePoll(() => api.alarms("Active"), 6000);
  const { data: history } = usePoll(() => api.history("All", 5), 6000);
  const { data: runs } = usePoll(() => api.runs("All"), 6000);

  return (
    <div className="flex gap-4.5 p-5">
      <div className="min-w-0 flex-1">
        <div className="mb-4.5 grid grid-cols-5 gap-3">
          <StatCard label="Online Devices" value={`${summary?.onlineDevices ?? "—"} / 20`} color="#34d399" />
          <StatCard label="Active Outputs" value={summary?.activeOutputs ?? "—"} color="#2dd4ee" />
          <StatCard label="Total Power" value={summary?.totalPowerW ?? "—"} unit=" W" color="#2dd4ee" />
          <StatCard label="Running Scenarios" value={summary?.runningScenarios ?? "—"} />
          <StatCard label="Active Alarms" value={summary?.activeAlarms ?? "—"} color="#fbbf24" />
        </div>

        <div className="flex gap-4">
          {(racks ?? []).map((rk) => (
            <div key={rk.id} className="flex-1 overflow-hidden rounded-[10px] border border-line bg-rack">
              <div className="flex items-center justify-between border-b border-line bg-panel px-3.5 py-3">
                <div>
                  <div className="font-mono text-[13px] font-bold">{rk.name}</div>
                  <div className="text-[10px] text-faint">{rk.loc}</div>
                </div>
                <div className="font-mono text-[10px] text-muted">
                  {rk.onCount}/{rk.count} online
                </div>
              </div>
              <div className="flex flex-col gap-[7px] p-2.5">
                {rk.units.map((u) => (
                  <UnitCard key={u.name} u={u} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex w-[320px] flex-none flex-col gap-3.5">
        <div className="overflow-hidden rounded-[10px] border border-line bg-panel">
          <div className="flex items-center gap-1.5 border-b border-line px-3.5 py-2.5 text-[12px] font-semibold">
            <span className="h-1.5 w-1.5 rounded-full bg-amber" />
            Recent Alarms
          </div>
          <div className="p-1.5">
            {(alarmsData?.rows ?? []).slice(0, 4).map((a) => (
              <div key={a.id} className="flex flex-col gap-1 rounded-md p-2.5">
                <div className="flex items-center justify-between">
                  <span
                    className="rounded font-mono text-[9px] font-semibold tracking-wider"
                    style={{ color: SEV_COLOR[a.sev], border: `1px solid ${SEV_COLOR[a.sev]}55`, padding: "1px 5px" }}
                  >
                    {a.sev.toUpperCase()}
                  </span>
                  <span className="font-mono text-[10px] text-faint">{a.time}</span>
                </div>
                <div className="text-[11.5px] leading-snug text-[#cfd6e2]">
                  <b className="font-mono text-white">{a.unit}</b> · {a.msg}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="overflow-hidden rounded-[10px] border border-line bg-panel">
          <div className="flex items-center gap-1.5 border-b border-line px-3.5 py-2.5 text-[12px] font-semibold">
            <span className="h-1.5 w-1.5 rounded-full bg-cyan" />
            Recent Command Activity
          </div>
          <div className="p-1.5">
            {(history?.rows ?? []).map((c) => (
              <div key={c.cid} className="flex items-center gap-2 px-2.5 py-1.5 font-mono">
                <span className="w-[54px] flex-none text-[9.5px] text-faint">{c.t}</span>
                <span className="min-w-0 flex-1 truncate text-[11px] text-[#cfd6e2]">{c.tpl}</span>
                <span
                  className="rounded font-mono text-[10px] font-semibold"
                  style={{
                    color: c.st === "OK" ? "#34d399" : c.st === "WARN" ? "#fbbf24" : "#f87171",
                    border: `1px solid ${c.st === "OK" ? "#34d39955" : c.st === "WARN" ? "#fbbf2455" : "#f8717155"}`,
                    padding: "1px 6px",
                  }}
                >
                  {c.st}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="overflow-hidden rounded-[10px] border border-line bg-panel">
          <div className="flex items-center gap-1.5 border-b border-line px-3.5 py-2.5 text-[12px] font-semibold">
            <span className="h-1.5 w-1.5 rounded-full bg-green" />
            Recent Scenario Runs
          </div>
          <div className="p-2">
            {(runs ?? []).slice(0, 4).map((r) => (
              <div key={r.id} className="flex flex-col gap-1.5 p-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11.5px] font-semibold text-[#cfd6e2]">{r.scenario}</span>
                  <span className="font-mono text-[10px] font-semibold" style={{ color: RUN_COLOR[r.status] }}>
                    {r.status}
                  </span>
                </div>
                <div className="h-1 overflow-hidden rounded-full bg-line">
                  <div className="h-full" style={{ width: `${r.prog}%`, background: RUN_COLOR[r.status] }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
