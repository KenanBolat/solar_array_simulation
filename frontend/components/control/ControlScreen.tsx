"use client";
import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { usePageHeader } from "@/lib/header-context";
import { useUi } from "@/lib/ui-context";
import { Btn, Eyebrow, Panel, SEV_COLOR, STATUS_COLOR, HIST_COLOR } from "@/components/ui";
import { Sparkline } from "@/components/Sparkline";
import { TerminalModal } from "./TerminalModal";
import { FrontPanelModal } from "./FrontPanelModal";

const RANGES = ["5 min", "30 min", "1 hour", "24 hours", "Custom"];
const PROFILES = ["BOL_GEO_28V", "EOL_LEO_24V", "Eclipse cycle"];

export function ControlScreen({ unitName }: { unitName: string }) {
  const { ask, notify } = useUi();
  const [range, setRange] = useState("30 min");
  const [showTerminal, setShowTerminal] = useState(false);
  const [showFrontPanel, setShowFrontPanel] = useState(false);
  const [voltInput, setVoltInput] = useState("28.0");
  const [currInput, setCurrInput] = useState("5.0");
  const [profile, setProfile] = useState(PROFILES[0]);

  const { data: unit, reload: reloadUnit } = usePoll(() => api.unit(unitName), 3000, [unitName]);
  const { data: telemetry, reload: reloadTelemetry } = usePoll(() => api.telemetry(unitName, range), 4000, [unitName, range]);
  const { data: history, reload: reloadHistory } = usePoll(() => api.history("All", 50), 4000, [unitName]);
  const { data: alarmsData, reload: reloadAlarms } = usePoll(() => api.alarms("Active"), 5000);

  usePageHeader(`Simulator Control · ${unitName}`, unit?.pos);

  const reloadAll = () => { reloadUnit(); reloadTelemetry(); reloadHistory(); reloadAlarms(); };

  if (!unit) return <div className="p-5 text-muted">Loading {unitName}…</div>;

  const co = unit.output;
  const statusColor = STATUS_COLOR[unit.statusColor];
  const rows = (history?.rows ?? []).filter((h) => h.dev === unitName).slice(0, 6);

  const toggleOutput = () => {
    if (co) {
      ask({
        title: `Disable Output — ${unitName}`,
        message: `This sets OUTP:STAT OFF on ${unitName}. The simulated array output will drop to 0 V / 0 A. Confirm to send the validated command.`,
        confirmLabel: "Disable Output", danger: true,
        onConfirm: async () => { await api.setOutput(unitName, false); notify(`Output disabled · ${unitName}`); reloadAll(); },
      });
    } else {
      ask({
        title: `Enable Output — ${unitName}`,
        message: "This sets OUTP:STAT ON, energising the simulated solar array output at the configured setpoint.",
        confirmLabel: "Enable Output", danger: false,
        onConfirm: async () => { await api.setOutput(unitName, true); notify(`Output enabled · ${unitName}`); reloadAll(); },
      });
    }
  };

  const applySetpoint = () => {
    const v = parseFloat(voltInput);
    const c = parseFloat(currInput);
    if (!isFinite(v) || !isFinite(c)) { notify("Enter valid numbers for voltage and current"); return; }
    ask({
      title: `Apply Setpoint — ${unitName}`,
      message: `Set voltage to ${v.toFixed(1)} V and current limit to ${c.toFixed(1)} A. Dispatched as validated commands and logged.`,
      confirmLabel: "Apply Setpoint", danger: false,
      onConfirm: async () => { await api.setSetpoint(unitName, { voltage: v, currentLimit: c }); notify(`Setpoint applied · ${unitName}`); reloadAll(); },
    });
  };

  const applyProfile = () => {
    ask({
      title: `Apply Profile — ${profile}`,
      message: `Apply simulator profile "${profile}" to ${unitName}. This overwrites the current I-V curve parameters.`,
      confirmLabel: "Apply Profile", danger: false,
      onConfirm: async () => { await api.applyProfile(unitName, profile); notify(`Profile applied · ${profile}`); reloadAll(); },
    });
  };

  const doShutdown = () => {
    ask({
      title: `Safe Shutdown — ${unitName}`,
      message: "Initiates the ramped safe-shutdown sequence: output disabled, current limit reduced to 0, device set to standby. This is a high-risk safety action and will be logged with full traceability.",
      confirmLabel: "Execute Safe Shutdown", danger: true,
      onConfirm: async () => { await api.shutdown(unitName); notify(`Safe shutdown executed · ${unitName}`); reloadAll(); },
    });
  };

  return (
    <div className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="h-[11px] w-[11px] rounded-full" style={{ background: statusColor, boxShadow: `0 0 10px ${statusColor}66` }} />
          <h2 className="m-0 font-mono text-[20px] font-bold">{unit.name}</h2>
          <span className="font-mono text-[12px] text-muted">{unit.pos}</span>
        </div>
        <div className="flex items-center gap-2.5">
          <Btn onClick={() => setShowTerminal(true)}>&gt;_ Command Terminal</Btn>
          <Btn onClick={() => setShowFrontPanel(true)}>⌨ Virtual Front Panel</Btn>
          <Link href="/scenarios/builder" className="rounded-md border border-cyan/40 bg-cyan/[0.08] px-3.5 py-2 text-[12px] font-semibold text-cyan">
            View Scenario Builder →
          </Link>
        </div>
      </div>

      <div className="grid grid-cols-[300px_1fr] items-start gap-4">
        <div className="flex flex-col gap-3.5">
          <Panel className="p-3.5">
            <Eyebrow>Device Identity</Eyebrow>
            <div className="flex flex-col gap-2 font-mono text-[11.5px]">
              <Row k="Name" v={unit.name} />
              <Row k="Location" v={unit.pos} />
              <Row k="Connection" v={<span style={{ color: unit.online ? "#34d399" : "#f87171" }}>● {unit.connection}</span>} />
              <Row k="IP Address" v={<span className="text-[10.5px]">{unit.ipAddress ? `${unit.ipAddress}:${unit.scpiPort}` : "—"}</span>} />
              <Row k="MAC Address" v={<span className="text-[10px]">{unit.macAddress || "—"}</span>} />
              <Row k="Last comm" v={unit.lastComm} />
              <Row k="Firmware" v={unit.firmware} />
              <Row k="Mode" v={<span className="text-amber">{unit.mode}</span>} />
            </div>
          </Panel>

          <Panel className="p-3.5">
            <Eyebrow>Safe Controls</Eyebrow>
            <div className="flex flex-col gap-2.5">
              <div
                onClick={toggleOutput}
                className="flex cursor-pointer items-center justify-center gap-2 rounded-md border py-2.5 text-[13px] font-semibold"
                style={{ color: co ? "#f87171" : "#04130c", background: co ? "transparent" : "#34d399", borderColor: co ? "#f8717188" : "#34d399" }}
              >
                <span className="text-[14px]">⏻</span>{co ? "Disable Output" : "Enable Output"}
              </div>
              <div className="flex gap-2">
                <div className="flex-1">
                  <label className="mb-1 block text-[10px] text-faint">Set Voltage (V)</label>
                  <input value={voltInput} onChange={(e) => setVoltInput(e.target.value)}
                    className="w-full rounded-md border border-line2 bg-bg px-2.5 py-1.5 font-mono text-[13px] text-ink" />
                </div>
                <div className="flex-1">
                  <label className="mb-1 block text-[10px] text-faint">Current Limit (A)</label>
                  <input value={currInput} onChange={(e) => setCurrInput(e.target.value)}
                    className="w-full rounded-md border border-line2 bg-bg px-2.5 py-1.5 font-mono text-[13px] text-ink" />
                </div>
              </div>
              <Btn variant="primary" onClick={applySetpoint}>Apply Setpoint</Btn>
              <div>
                <label className="mb-1 block text-[10px] text-faint">Apply Profile</label>
                <div className="flex gap-2">
                  <select value={profile} onChange={(e) => setProfile(e.target.value)}
                    className="w-full rounded-md border border-line2 bg-bg px-2.5 py-1.5 text-[12px] text-ink">
                    {PROFILES.map((p) => <option key={p}>{p}</option>)}
                  </select>
                  <Btn onClick={applyProfile}>Apply</Btn>
                </div>
              </div>
              <div className="flex gap-2">
                <Btn className="flex-1" onClick={async () => { await api.refresh(unitName); notify(`Measurement refreshed · ${unitName}`); reloadAll(); }}>Refresh</Btn>
                <Btn className="flex-1" onClick={async () => { const r = await api.identify(unitName); notify(r.idn); }}>Query *IDN?</Btn>
              </div>
              <button onClick={doShutdown} className="rounded-md border border-red bg-red/10 py-2.5 text-[12px] font-bold tracking-wide text-red">
                ⏻ SAFE SHUTDOWN
              </button>
            </div>
          </Panel>
        </div>

        <div className="flex flex-col gap-3.5">
          <div className="grid grid-cols-6 gap-2.5">
            <MiniStat label="OUTPUT" value={unit.online ? (co ? "ON" : "OFF") : "—"} color={co ? "#2dd4ee" : "#5c6678"} />
            <MiniStat label="VOLTAGE" value={unit.voltage != null ? unit.voltage.toFixed(1) : "—"} suffix={unit.voltage != null ? " V" : undefined} />
            <MiniStat label="CURRENT" value={unit.current != null ? unit.current.toFixed(1) : "—"} suffix={unit.current != null ? " A" : undefined} />
            <MiniStat label="POWER" value={unit.power != null ? unit.power.toFixed(1) : "—"} suffix={unit.power != null ? " W" : undefined} color="#2dd4ee" />
            <MiniStat label="DEVICE" value={unit.deviceState} small color={co ? "#34d399" : "#8a95a8"} />
            <MiniStat label="ALARM" value={unit.alarm === "warning" ? "Warning" : "Normal"} small color={unit.alarm === "warning" ? "#fbbf24" : "#34d399"} />
          </div>

          <Panel className="p-3.5">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-[12px] font-semibold">Live Measurements</div>
              <div className="flex gap-1.5">
                {RANGES.map((r) => (
                  <div key={r} onClick={() => setRange(r)}
                    className="cursor-pointer rounded-md px-2.5 py-1 text-[11px] font-semibold"
                    style={{ color: r === range ? "#04121a" : "#8a95a8", background: r === range ? "#2dd4ee" : "transparent", border: `1px solid ${r === range ? "#2dd4ee" : "#2c3543"}` }}>
                    {r}
                  </div>
                ))}
              </div>
            </div>
            <div className="flex flex-col gap-2.5">
              <div>
                <div className="mb-1 font-mono text-[10px] text-muted">VOLTAGE · V</div>
                <Sparkline values={telemetry?.v ?? []} color="#2dd4ee" unit=" V" decimals={2} />
              </div>
              <div>
                <div className="mb-1 font-mono text-[10px] text-muted">CURRENT · A</div>
                <Sparkline values={telemetry?.i ?? []} color="#34d399" unit=" A" decimals={2} />
              </div>
              <div>
                <div className="mb-1 font-mono text-[10px] text-muted">POWER · W</div>
                <Sparkline values={telemetry?.p ?? []} color="#fbbf24" unit=" W" decimals={1} />
              </div>
            </div>
          </Panel>

          <div className="grid grid-cols-[1.6fr_1fr] gap-3.5">
            <Panel title="Command Activity" className="overflow-hidden">
              <div className="grid gap-2.5 border-b border-line px-3.5 py-1.5 font-mono text-[9px] uppercase tracking-wider text-faint" style={{ gridTemplateColumns: "62px 56px 1fr 50px 70px" }}>
                <span>Time</span><span>User</span><span>Action</span><span>Status</span><span>Corr. ID</span>
              </div>
              {rows.length === 0 && <div className="px-3.5 py-4 text-[11px] text-faint">No commands logged for this unit yet.</div>}
              {rows.map((c) => (
                <div key={c.cid} className="grid items-center gap-2.5 border-b border-[#161b24] px-3.5 py-2 font-mono text-[10.5px]" style={{ gridTemplateColumns: "62px 56px 1fr 50px 70px" }}>
                  <span className="text-muted">{c.t}</span>
                  <span className="text-[#cfd6e2]">{c.user}</span>
                  <span className="truncate text-ink">{c.tpl}</span>
                  <span>
                    <span className="rounded px-1.5 py-0.5 text-[10px] font-semibold" style={{ color: HIST_COLOR[c.st], border: `1px solid ${HIST_COLOR[c.st]}55` }}>{c.st}</span>
                  </span>
                  <span className="text-faint">{c.cid}</span>
                </div>
              ))}
            </Panel>
            <Panel title="Alarm Panel" className="overflow-hidden">
              <div className="p-1.5">
                {(alarmsData?.rows ?? []).map((a) => (
                  <div key={a.id} className="flex flex-col gap-1.5 border-b border-[#161b24] p-2">
                    <div className="flex items-center justify-between">
                      <span className="rounded font-mono text-[9.5px] font-semibold" style={{ color: SEV_COLOR[a.sev], border: `1px solid ${SEV_COLOR[a.sev]}55`, padding: "2px 6px" }}>{a.sev.toUpperCase()}</span>
                      <span className="font-mono text-[9.5px] text-faint">{a.time}</span>
                    </div>
                    <div className="text-[11px] leading-snug text-[#cfd6e2]">{a.msg}</div>
                    {a.ackd ? (
                      <span className="text-[10px] font-semibold text-green">✓ Acknowledged</span>
                    ) : (
                      <button onClick={async () => { await api.ackAlarm(a.id); notify(`Acknowledged · ${a.unit}`); reloadAlarms(); }}
                        className="self-start rounded border border-line2 bg-panel2 px-2.5 py-1 text-[10px] font-semibold text-ink">
                        Acknowledge
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </div>
      </div>

      {showTerminal && <TerminalModal unitName={unitName} onClose={() => setShowTerminal(false)} onChanged={reloadAll} />}
      {showFrontPanel && <FrontPanelModal unitName={unitName} onClose={() => setShowFrontPanel(false)} onChanged={reloadAll} />}
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex justify-between">
      <span className="text-faint">{k}</span>
      <span>{v}</span>
    </div>
  );
}

function MiniStat({ label, value, suffix, color, small }: { label: string; value: string; suffix?: string; color?: string; small?: boolean }) {
  return (
    <div className="rounded-[9px] border border-line bg-panel px-3.5 py-3">
      <div className="mb-1 text-[10px] text-muted">{label}</div>
      <div className={`font-mono font-bold ${small ? "text-[14px] mt-0.5" : "text-[19px]"}`} style={{ color: color || "#e6eaf2" }}>
        {value}{suffix && <span className="text-[11px] text-faint">{suffix}</span>}
      </div>
    </div>
  );
}
