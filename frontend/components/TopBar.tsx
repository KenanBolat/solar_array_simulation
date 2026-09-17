"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { useHeaderState } from "@/lib/header-context";

export function TopBar() {
  const { title, sub } = useHeaderState();
  const { data: summary } = usePoll(() => api.summary(), 5000);
  const [clock, setClock] = useState("");

  useEffect(() => {
    const tick = () => setClock(new Date().toISOString().slice(11, 16) + " UTC");
    tick();
    const t = setInterval(tick, 15000);
    return () => clearInterval(t);
  }, []);

  const online = summary?.onlineDevices ?? "—";
  const total = summary?.configuredUnits ?? "—";
  const alarms = summary?.activeAlarms ?? 0;

  return (
    <header className="flex h-[54px] flex-none items-center gap-4 border-b border-line bg-[#0e1117] px-5">
      <div className="min-w-0">
        <div className="text-[14px] font-semibold leading-tight">{title}</div>
        {sub && <div className="font-mono text-[11px] text-faint">{sub}</div>}
      </div>
      <div className="flex-1" />
      <div className="flex items-center gap-1.5 rounded-md border border-green/30 bg-green/10 px-2.5 py-1">
        <span className="h-[7px] w-[7px] animate-scpulse rounded-full bg-green" />
        <span className="font-mono text-[11px] font-semibold text-green">{online}/{total} ONLINE</span>
      </div>
      {alarms > 0 && (
        <div className="flex items-center gap-1.5 rounded-md border border-amber/30 bg-amber/10 px-2.5 py-1">
          <span className="font-mono text-[11px] font-semibold text-amber">{alarms} ALARM{alarms === 1 ? "" : "S"}</span>
        </div>
      )}
      <div className="flex items-center gap-1.5 rounded-md border border-cyan/35 bg-cyan/[0.06] px-2.5 py-1" title="Commands are dispatched to the instruments as SCPI and confirmed with *OPC? / SYST:ERR? / readback">
        <span className="text-[10px] font-semibold tracking-wider text-cyan">LIVE SCPI</span>
      </div>
      <div className="border-l border-line pl-3.5 font-mono text-[11px] text-faint">{clock}</div>
    </header>
  );
}
