"use client";
import Link from "next/link";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { STATUS_COLOR } from "@/components/ui";

export default function IntroPage() {
  const { data: racks } = usePoll(() => api.racks(), 10000);
  const { data: summary } = usePoll(() => api.summary(), 10000);

  const stats = [
    { label: "Configured Units", value: summary?.configuredUnits ?? "—", color: "#e6eaf2" },
    { label: "Online", value: summary?.onlineDevices ?? "—", color: "#34d399" },
    { label: "Active Scenarios", value: summary?.runningScenarios ?? "—", color: "#2dd4ee" },
    { label: "Warnings", value: 1, color: "#fbbf24" },
    { label: "Critical Alarms", value: summary?.criticalAlarms ?? "—", color: "#34d399" },
  ];

  return (
    <div
      className="flex min-h-screen items-center justify-center bg-eng-grid px-6 py-10"
      style={{ backgroundColor: "#0b0d11" }}
    >
      <div className="w-full max-w-[1100px]">
        <div className="mb-[22px] flex items-center gap-3">
          <div className="flex h-[42px] w-[42px] items-center justify-center rounded-[9px] border border-cyan/40 bg-cyan/10">
            <div className="h-[18px] w-[18px] rounded-[3px] border-[2.5px] border-cyan" />
          </div>
          <div className="font-mono text-[11px] font-semibold tracking-[0.14em] text-cyan">
            GROUND SEGMENT · POWER TEST
          </div>
        </div>
        <h1 className="mb-3 text-[40px] font-bold leading-[1.08] tracking-tight">
          Solar Array Simulator
          <br />
          Control Platform
        </h1>
        <p className="mb-[30px] max-w-[560px] text-[16px] leading-relaxed text-muted">
          Monitor, control, and automate solar array simulator test scenarios across distributed laboratory racks.
        </p>

        <div className="grid grid-cols-[1fr_360px] items-start gap-6">
          <div className="flex gap-4">
            {(racks ?? []).map((rk) => (
              <div key={rk.id} className="flex-1 rounded-[10px] border border-line bg-panel p-3.5">
                <div className="mb-2.5 flex items-center justify-between">
                  <div className="font-mono text-[12px] font-bold tracking-wide">{rk.name}</div>
                  <div className="text-[10px] text-faint">
                    {rk.onCount}/{rk.count}
                  </div>
                </div>
                <div className="flex flex-col gap-1.5">
                  {rk.units.map((u) => {
                    const c = STATUS_COLOR[u.statusColor];
                    return (
                      <div
                        key={u.name}
                        className="flex h-[14px] items-center rounded-sm pl-1.5"
                        style={{ background: `${c}22`, borderLeft: `3px solid ${c}` }}
                      >
                        <span className="font-mono text-[9px] font-semibold text-[#a9b2c0]">{u.name}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          <div className="flex flex-col gap-3.5">
            <div className="grid grid-cols-2 gap-2.5">
              {stats.map((c) => (
                <div key={c.label} className="rounded-[9px] border border-line bg-panel px-3.5 py-3">
                  <div className="font-mono text-[19px] font-semibold" style={{ color: c.color }}>
                    {c.value}
                  </div>
                  <div className="mt-0.5 text-[11px] text-muted">{c.label}</div>
                </div>
              ))}
            </div>
            <Link
              href="/overview"
              className="block w-full rounded-[9px] bg-cyan px-4 py-[15px] text-center text-[15px] font-bold text-[#04121a] shadow-[0_6px_22px_#2dd4ee33]"
            >
              Enter Control Center →
            </Link>
            <div className="flex items-start gap-2.5 rounded-lg border border-red/20 bg-red/[0.05] px-3.5 py-3">
              <span className="flex-none text-[15px] leading-tight text-red">⚠</span>
              <div className="text-[11.5px] leading-relaxed text-[#c9a9a9]">
                Software control does not replace physical interlocks or emergency shutdown systems.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
