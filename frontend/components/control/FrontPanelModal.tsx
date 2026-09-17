"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { useUi } from "@/lib/ui-context";

const FP_MENU = ["Output On/Off", "Set Voltage", "Set Current Limit", "Mode FIX / SAS", "Clear Protection", "I/O Configuration"];
const MODE_LABEL: Record<string, string> = { FIX: "FIX", SAS: "SAS", TABL: "TABL" };

type Mode = "meter" | "entry" | "menu";

function shortError(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e);
  const m = msg.match(/rejected by instrument · (-?\d+),"([^"]*)"/);
  if (m) return `REJECTED ${m[1]}\n${m[2].toUpperCase()}`;
  if (/unreachable/i.test(msg)) return "UNREACHABLE\nNO CONNECTION TO INSTRUMENT";
  if (/timeout/i.test(msg)) return "TIMEOUT\nINSTRUMENT DID NOT REPLY";
  return "COMMAND FAILED\n" + msg.slice(0, 40).toUpperCase();
}

export function FrontPanelModal({ unitName, onClose, onChanged }: { unitName: string; onClose: () => void; onChanged: () => void }) {
  const { notify } = useUi();
  const { data: unit, reload } = usePoll(() => api.unit(unitName), 1500, [unitName]);

  const [mode, setMode] = useState<Mode>("meter");
  const [field, setField] = useState<"VOLTAGE" | "CURRENT" | null>(null);
  const [buf, setBuf] = useState("");
  const [menuIdx, setMenuIdx] = useState(0);
  const [flash, setFlash] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [voltSet, setVoltSet] = useState(0);
  const [currSet, setCurrSet] = useState(0);

  // The instrument is the source of truth — follow whatever the poller mirrors back.
  useEffect(() => {
    if (unit) { setVoltSet(unit.voltageSetpoint); setCurrSet(unit.currentLimit); }
  }, [unit?.voltageSetpoint, unit?.currentLimit]);

  const doFlash = (msg: string, ms = 1400) => {
    setFlash(msg);
    if (flashTimer.current) clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setFlash(null), ms);
  };

  if (!unit) return null;
  const outputOn = unit.output;
  const online = unit.online;
  const chan = unit.channel;
  const opMode = unit.opMode ? MODE_LABEL[unit.opMode] ?? unit.opMode : "—";

  const send = async (label: string, fn: () => Promise<unknown>, okFlash: string) => {
    if (busy) return;
    setBusy(true);
    try {
      await fn();
      doFlash(okFlash);
      notify(`Front panel · ${label} · OK`);
    } catch (e) {
      doFlash(shortError(e), 2600);
      notify(`Front panel · ${label} · ${e instanceof Error ? e.message : "failed"}`);
    } finally {
      setBusy(false);
      onChanged(); reload();
    }
  };

  const toggleOutput = () =>
    send(`OUTP ${!outputOn ? "ON" : "OFF"},(@${chan})`, () => api.setOutput(unitName, !outputOn),
      !outputOn ? "OUTPUT ENABLED" : "OUTPUT DISABLED");

  const toggleMode = () => {
    const next = unit.opMode === "SAS" ? "FIX" : "SAS";
    return send(`CURR:MODE ${next},(@${chan})`, () => api.setMode(unitName, next), `MODE ${next} SET`);
  };

  const clearProtection = () =>
    send(`OUTP:PROT:CLE (@${chan})`, () => api.clearProtection(unitName), "PROTECTION CLEARED");

  const func = (name: string) => {
    if (name === "voltage") { setMode("entry"); setField("VOLTAGE"); setBuf(""); }
    else if (name === "current") { setMode("entry"); setField("CURRENT"); setBuf(""); }
    else if (name === "meter") setMode("meter");
    else if (name === "menu") setMode("menu");
    else if (name === "back") { setMode("meter"); setBuf(""); }
    else if (name === "channel") doFlash(`CHANNEL (@${chan}) · FIXED IN CONFIG`);
    else if (name === "help") doFlash("USE NAV + SEL · DIGITS THEN ENTER");
    else if (name === "error") doFlash(unit.questionable ? `STAT:QUES:COND? +${unit.questionable}\nPROTECTION TRIPPED` : "STAT:QUES:COND? +0\nNO FAULTS");
    else if (name === "onoff") toggleOutput();
  };

  const input = (k: string) => {
    if (mode !== "entry") { doFlash("PRESS VOLTAGE / CURRENT FIRST"); return; }
    setBuf((b) => {
      if (/[0-9]/.test(k)) return b + k;
      if (k === ".") return b.includes(".") ? b : (b === "" || b === "-" ? b + "0." : b + ".");
      if (k === "E") return b.includes("E") || b === "" ? b : b + "E";
      if (k === "+/-") return b.startsWith("-") ? b.slice(1) : "-" + b;
      if (k === "back") return b.slice(0, -1);
      return b;
    });
  };

  const enter = async () => {
    if (mode !== "entry") { doFlash("NOTHING TO ENTER"); return; }
    const val = parseFloat(buf);
    if (isNaN(val)) { doFlash("INVALID ENTRY"); return; }
    setMode("meter"); setBuf("");
    if (field === "VOLTAGE") {
      const v = Math.max(0, Math.min(32, val));
      await send(`VOLT ${v},(@${chan})`, () => api.setSetpoint(unitName, { voltage: v }), `VOLT ${v.toFixed(2)} V SET · READBACK OK`);
    } else {
      const a = Math.max(0, Math.min(6, val));
      await send(`CURR ${a},(@${chan})`, () => api.setSetpoint(unitName, { currentLimit: a }), `CURR ${a.toFixed(2)} A SET · READBACK OK`);
    }
  };

  const nav = async (dir: "up" | "down" | "left" | "right" | "sel") => {
    if (mode === "menu") {
      if (dir === "up") setMenuIdx((i) => (i + FP_MENU.length - 1) % FP_MENU.length);
      else if (dir === "down") setMenuIdx((i) => (i + 1) % FP_MENU.length);
      else if (dir === "sel") {
        if (menuIdx === 0) func("onoff");
        else if (menuIdx === 1) { setMode("entry"); setField("VOLTAGE"); setBuf(""); }
        else if (menuIdx === 2) { setMode("entry"); setField("CURRENT"); setBuf(""); }
        else if (menuIdx === 3) toggleMode();
        else if (menuIdx === 4) clearProtection();
        else doFlash(`${unit.ipAddress}:${unit.scpiPort} ${unit.transport.toUpperCase()}\n${unit.visa}`, 3000);
      }
      return;
    }
    if (dir === "up" || dir === "down") {
      const d = dir === "up" ? 0.1 : -0.1;
      if (field === "CURRENT") {
        const a = Math.max(0, Math.min(6, +(currSet + d).toFixed(2)));
        await send(`CURR ${a},(@${chan})`, () => api.setSetpoint(unitName, { currentLimit: a }), `CURR ${a.toFixed(2)} A SET`);
      } else {
        const v = Math.max(0, Math.min(32, +(voltSet + d).toFixed(2)));
        await send(`VOLT ${v},(@${chan})`, () => api.setSetpoint(unitName, { voltage: v }), `VOLT ${v.toFixed(2)} V SET`);
      }
    } else if (dir === "sel") setMode("meter");
  };

  const fmtV = unit.voltage != null ? `${unit.voltage.toFixed(3)} V` : "--.--- V";
  const fmtI = unit.current != null ? `${unit.current.toFixed(3)} A` : "--.--- A";
  const fmtP = unit.power != null ? `${unit.power.toFixed(2)} W` : "---.-- W";
  const headerRow = `${unitName}  CH${chan}      OUTPUT ${online ? (outputOn ? "ON" : "OFF") : "?"}`;

  let lcdRows: { text: string; big?: boolean; color?: string }[];
  if (mode === "entry") {
    const rng = field === "VOLTAGE" ? "0 - 32 V" : "0 - 6 A";
    lcdRows = [
      { text: "SET " + field + (unit.opMode === "SAS" ? "   (SAS MODE: WILL BE REJECTED 315)" : ""), color: unit.opMode === "SAS" ? "#fbbf24" : "#7be8c8" },
      { text: "> " + (buf || "") + "█", big: true, color: "#9affd9" },
      { text: `Range ${rng}  Enter=apply`, color: "#4fbf9c" },
    ];
  } else if (mode === "menu") {
    lcdRows = [{ text: "MAIN MENU", color: "#7be8c8" }];
    FP_MENU.forEach((m, i) => lcdRows.push({ text: (i === menuIdx ? "▸ " : "  ") + m, color: i === menuIdx ? "#9affd9" : "#3f9c80" }));
  } else if (flash) {
    const lines = flash.split("\n");
    const bad = /REJECTED|UNREACHABLE|TIMEOUT|FAILED|TRIPPED/.test(lines[0]);
    lcdRows = [{ text: `${unitName}   CH${chan}`, color: "#7be8c8" }, ...lines.map((t) => ({ text: "  " + t, color: bad ? "#fbbf24" : "#9affd9" }))];
  } else if (!online) {
    lcdRows = [
      { text: headerRow, color: "#fbbf24" },
      { text: "NO COMMS", big: true, color: "#fbbf24" },
      { text: `${unit.transport.toUpperCase()} ${unit.ipAddress}${unit.transport === "socket" ? ":" + unit.scpiPort : ""}`, color: "#b48a24" },
      { text: (unit.lastError ?? "no reply").slice(0, 96), color: "#b48a24" },
    ];
  } else {
    lcdRows = [
      { text: headerRow, color: outputOn ? "#7be8c8" : "#4fbf9c" },
      { text: `${fmtV}   ${fmtI}`, big: true, color: "#9affd9" },
      { text: `${fmtP}   ${opMode}   Lim ${currSet.toFixed(1)}A${unit.questionable ? "   PROT!" : ""}`, color: unit.questionable ? "#fbbf24" : "#4fbf9c" },
    ];
  }

  const keypad: [string, string][] = [
    ["7", "7"], ["8", "8"], ["9", "9"], ["▲", "up"],
    ["4", "4"], ["5", "5"], ["6", "6"], ["▼", "down"],
    ["1", "1"], ["2", "2"], ["3", "3"], ["E", "E"],
    ["0", "0"], [".", "."], ["+/−", "+/-"], ["⌫", "back"],
  ];
  const softBtns: [string, string][] = [["Meter", "meter"], ["Menu", "menu"], ["Channel", "channel"], ["Back", "back"], ["Help", "help"], ["Error", "error"]];
  const keyBase = "flex items-center justify-center rounded-md cursor-pointer font-mono text-[14px] font-semibold select-none";

  return (
    <div data-testid="front-panel-modal" className="fixed inset-0 z-[55] flex items-center justify-center bg-[#05070ad8] p-6">
      <div className="w-[980px] max-w-full">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="text-[13px] font-semibold">Virtual Front Panel</span>
            <span className="font-mono text-[11px] text-faint">{unitName} · E4360A ch{chan} · live SCPI over {unit.transport === "socket" ? "socket" : "VXI-11"}</span>
          </div>
          <button onClick={onClose} className="flex h-[30px] w-[30px] items-center justify-center rounded-md border border-line2 bg-panel2 text-[16px] text-ink">✕</button>
        </div>

        <div
          className="flex flex-col gap-4 rounded-[14px] border border-line2 p-[18px] shadow-[0_30px_80px_rgba(0,0,0,0.6)]"
          style={{ background: "linear-gradient(180deg,#191d24,#12151b)" }}
        >
          <div className="flex items-stretch gap-4">
            <div className="flex w-[88px] flex-none flex-col items-center justify-between py-1">
              <div className="flex h-[46px] w-[46px] items-center justify-center rounded-lg border border-line2 bg-[#0e1117]">
                <div className="h-[22px] w-[14px] rounded-sm border-2 border-faint" />
              </div>
              <div className="flex flex-col items-center gap-2.5">
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: outputOn && online ? "#2dd4ee" : "#2c3543", boxShadow: outputOn && online ? "0 0 7px #2dd4ee" : "none" }} />
                  <span className="w-[34px] font-mono text-[9px] text-faint">OUT</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: online ? "#34d399" : "#f87171", boxShadow: online ? "0 0 6px #34d39988" : "0 0 6px #f8717188" }} />
                  <span className="w-[34px] font-mono text-[9px] text-faint">{online ? "LINK" : "LOST"}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: unit.questionable ? "#fbbf24" : "#2c3543", boxShadow: unit.questionable ? "0 0 7px #fbbf24" : "none" }} />
                  <span className="w-[34px] font-mono text-[9px] text-faint">PROT</span>
                </div>
              </div>
              <div className="text-center font-mono text-[8px] tracking-wider text-[#3a4456]">E4360A<br />MODULAR<br />SAS</div>
            </div>

            <div className="led-lcd flex min-h-[104px] min-w-[240px] flex-1 flex-col justify-center overflow-hidden rounded-lg border border-[#11352a] px-[18px] py-3.5" style={{ background: "#06120e", boxShadow: "inset 0 0 24px #00000080, inset 0 0 60px #0aff9e10", opacity: busy ? 0.75 : 1 }}>
              {lcdRows.map((r, idx) => (
                <div
                  key={idx}
                  className="whitespace-pre font-mono leading-relaxed"
                  style={{
                    color: r.color || "#5ef2c9", fontSize: r.big ? 19 : 12, fontWeight: r.big ? 600 : 400,
                    letterSpacing: r.big ? "0.02em" : "0.04em", textShadow: `0 0 8px ${r.color || "#5ef2c9"}55`,
                  }}
                >
                  {r.text}
                </div>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-4.5">
            <div className="grid grid-cols-2 grid-rows-3 gap-1.5" style={{ gridTemplateColumns: "repeat(2,68px)", gridAutoRows: 34 }}>
              {softBtns.map(([label, fn]) => (
                <div
                  key={fn}
                  onClick={() => func(fn)}
                  className="flex select-none items-center justify-center rounded-md border font-sans text-[11px] font-semibold"
                  style={{
                    background: "#1c222c",
                    borderColor: (fn === "menu" && mode === "menu") || (fn === "meter" && mode === "meter") ? "#2dd4ee" : "#2c3543",
                    color: fn === "error" ? (unit.questionable ? "#fbbf24" : "#8a95a8") : ((fn === "menu" && mode === "menu") || (fn === "meter" && mode === "meter")) ? "#fff" : "#cfd6e2",
                  }}
                >
                  {label}
                </div>
              ))}
            </div>

            <div className="flex flex-col items-center justify-center gap-1.5">
              <div className={`${keyBase} h-[38px] w-[38px] border border-line2 bg-[#1c222c] text-[13px] text-ink`} onClick={() => nav("up")}>▲</div>
              <div className="flex items-center gap-1.5">
                <div className={`${keyBase} h-[38px] w-[38px] border border-line2 bg-[#1c222c] text-[13px] text-ink`} onClick={() => nav("left")}>◄</div>
                <div className="flex h-[38px] w-[38px] select-none items-center justify-center rounded-full border border-cyan/40 bg-[#222a36] text-[10px] font-bold text-cyan" onClick={() => nav("sel")}>Sel</div>
                <div className={`${keyBase} h-[38px] w-[38px] border border-line2 bg-[#1c222c] text-[13px] text-ink`} onClick={() => nav("right")}>►</div>
              </div>
              <div className={`${keyBase} h-[38px] w-[38px] border border-line2 bg-[#1c222c] text-[13px] text-ink`} onClick={() => nav("down")}>▼</div>
            </div>

            <div className="grid w-[78px] gap-1.5" style={{ gridAutoRows: 42 }}>
              {([
                { label: "On/Off", fn: "onoff", active: outputOn && online },
                { label: "Voltage", fn: "voltage", active: field === "VOLTAGE" && mode === "entry" },
                { label: "Current", fn: "current", active: field === "CURRENT" && mode === "entry" },
              ] as const).map((b) => (
                <div
                  key={b.fn}
                  onClick={() => func(b.fn)}
                  className="flex select-none items-center justify-center rounded-md border font-sans text-[12px] font-semibold"
                  style={{
                    background: b.active ? "#2dd4ee1f" : "#1c222c",
                    borderColor: b.active ? "#2dd4ee" : "#2c3543",
                    color: b.active ? "#fff" : "#cfd6e2",
                  }}
                >
                  {b.label}
                </div>
              ))}
            </div>

            <div className="flex items-stretch gap-1.5">
              <div className="grid gap-1.5" style={{ gridTemplateColumns: "repeat(4,46px)", gridAutoRows: 38 }}>
                {keypad.map(([label, k]) => (
                  <div
                    key={k}
                    onClick={() => (k === "up" || k === "down" ? nav(k) : input(k))}
                    className={`${keyBase} border border-line2 bg-[#1c222c] text-ink`}
                  >
                    {label}
                  </div>
                ))}
              </div>
              <div
                onClick={enter}
                className="flex w-[46px] cursor-pointer select-none items-center justify-center rounded-md border border-cyan bg-cyan text-[12px] font-bold text-[#04121a]"
                style={{ writingMode: "vertical-rl", textOrientation: "mixed", letterSpacing: "0.08em" }}
              >
                Enter
              </div>
            </div>
          </div>
        </div>
        <div className="mt-2.5 text-center font-mono text-[11px] text-faint">
          Every key sends a real SCPI message to {unit.ipAddress} and waits for <b className="text-[#cfd6e2]">*OPC?</b> + <b className="text-[#cfd6e2]">SYST:ERR?</b> · readings are <b className="text-[#cfd6e2]">MEAS:VOLT?</b>/<b className="text-[#cfd6e2]">FETC:CURR?</b> polled every second · <b className="text-[#cfd6e2]">Error</b> shows STAT:QUES:COND?
        </div>
      </div>
    </div>
  );
}
