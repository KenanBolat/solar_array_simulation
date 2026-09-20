"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { useHeaderState } from "@/lib/header-context";

export function TopBar() {
  const { title, sub } = useHeaderState();
  const { data: summary } = usePoll(() => api.summary(), 5000);
  const { data: health } = usePoll(() => api.health(), 30000);
  const emulated = !!health && health.emulatedUnits > 0;
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
      {/* Says where commands are actually going. It used to read LIVE SCPI
          unconditionally, which told you nothing — the bundled emulators look
          identical from here unless the badge distinguishes them. */}
      <div className="flex items-center gap-1.5 rounded-md border px-2.5 py-1"
        style={{
          borderColor: emulated ? "#fbbf2459" : "#2dd4ee59",
          background: emulated ? "#fbbf240f" : "#2dd4ee0f",
        }}
        title={emulated
          ? `${health!.emulatedUnits} of ${health!.units} unit(s) point at the bundled emulators on 127.0.0.1, not real instruments. Real SCPI is still sent — to the emulator. Use “Apply fleet file” in Configuration to address them at the lab.`
          : "Every command is dispatched to the instruments as SCPI and confirmed with *OPC? / SYST:ERR? / readback"}>
        <span className="text-[10px] font-semibold tracking-wider"
          style={{ color: emulated ? "#fbbf24" : "#2dd4ee" }}>
          {emulated ? "EMULATED SCPI" : "LIVE SCPI"}
        </span>
      </div>
      <div className="border-l border-line pl-3.5 font-mono text-[11px] text-faint">{clock}</div>
    </header>
  );
}
