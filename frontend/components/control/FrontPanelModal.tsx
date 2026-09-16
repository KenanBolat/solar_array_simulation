"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { useUi } from "@/lib/ui-context";

const FP_MENU = ["Output On/Off", "Set Voltage", "Set Current Limit", "SAS Curve Mode", "Protection Limits", "I/O Configuration"];

type Mode = "meter" | "entry" | "menu";

export function FrontPanelModal({ unitName, onClose, onChanged }: { unitName: string; onClose: () => void; onChanged: () => void }) {
  const { notify } = useUi();
  const { data: unit, reload } = usePoll(() => api.unit(unitName), 1500, [unitName]);

  const [mode, setMode] = useState<Mode>("meter");
  const [field, setField] = useState<"VOLTAGE" | "CURRENT" | null>(null);
  const [buf, setBuf] = useState("");
  const [menuIdx, setMenuIdx] = useState(0);
  const [flash, setFlash] = useState<string | null>(null);
  const [chan, setChan] = useState(1);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [voltSet, setVoltSet] = useState(28.0);
  const [currSet, setCurrSet] = useState(5.0);

  useEffect(() => {
    if (unit) { setVoltSet(unit.voltageSetpoint); setCurrSet(unit.currentLimit); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [unit?.name]);

  const doFlash = (msg: string) => {
    setFlash(msg);
    if (flashTimer.current) clearTimeout(flashTimer.current);
    flashTimer.current = setTimeout(() => setFlash(null), 1400);
  };

  if (!unit) return null;
  const outputOn = unit.output;

  const commit = async (patch: { voltage?: number; currentLimit?: number }) => {
    await api.setSetpoint(unitName, patch);
    onChanged(); reload();
  };

  const toggleOutput = async () => {
    await api.setOutput(unitName, !outputOn);
    doFlash(!outputOn ? "OUTPUT ENABLED" : "OUTPUT DISABLED");
    notify(`Front panel · OUTP:STAT ${!outputOn ? "ON" : "OFF"}`);
    onChanged(); reload();
  };

  const func = (name: string) => {
    if (name === "voltage") { setMode("entry"); setField("VOLTAGE"); setBuf(""); }
    else if (name === "current") { setMode("entry"); setField("CURRENT"); setBuf(""); }
    else if (name === "meter") setMode("meter");
    else if (name === "menu") setMode("menu");
    else if (name === "back") { setMode("meter"); setBuf(""); }
    else if (name === "channel") { const c = chan === 1 ? 2 : 1; setChan(c); doFlash(`CHANNEL ${c} SELECTED`); }
    else if (name === "help") doFlash("USE NAV + SEL · DIGITS THEN ENTER");
    else if (name === "error") doFlash("NO ERROR  +0");
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
    if (field === "VOLTAGE") {
      const v = Math.max(0, Math.min(32, val));
      setVoltSet(v); setMode("meter"); setBuf("");
      doFlash(`VOLT ${v.toFixed(2)} V SET`); notify(`Front panel · VOLT ${v.toFixed(2)}`);
      await commit({ voltage: v });
    } else {
      const a = Math.max(0, Math.min(6, val));
      setCurrSet(a); setMode("meter"); setBuf("");
      doFlash(`CURR LIM ${a.toFixed(2)} A SET`); notify(`Front panel · CURR:LIM ${a.toFixed(2)}`);
      await commit({ currentLimit: a });
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
        else doFlash(FP_MENU[menuIdx].toUpperCase());
      }
      return;
    }
    if (dir === "up" || dir === "down") {
      const d = dir === "up" ? 0.1 : -0.1;
      if (field === "CURRENT") {
        const a = Math.max(0, Math.min(6, +(currSet + d).toFixed(2)));
        setCurrSet(a); await commit({ currentLimit: a });
      } else {
        const v = Math.max(0, Math.min(32, +(voltSet + d).toFixed(2)));
        setVoltSet(v); await commit({ voltage: v });
      }
    } else if (dir === "sel") setMode("meter");
  };

  const fpV = outputOn ? (unit.voltage ?? 0) : 0;
  const fpI = outputOn ? (unit.current ?? 0) : 0;
  const fpP = fpV * fpI;

  let lcdRows: { text: string; big?: boolean; color?: string }[];
  if (mode === "entry") {
    const unitLbl = field === "VOLTAGE" ? "V" : "A";
    const rng = field === "VOLTAGE" ? "0 - 32 V" : "0 - 6 A";
    lcdRows = [
      { text: "SET " + field, color: "#7be8c8" },
      { text: "> " + (buf || "") + "█", big: true, color: "#9affd9" },
      { text: `Range ${rng}  Enter=apply`, color: "#4fbf9c" },
    ];
  } else if (mode === "menu") {
    lcdRows = [{ text: "MAIN MENU", color: "#7be8c8" }];
    FP_MENU.forEach((m, i) => lcdRows.push({ text: (i === menuIdx ? "▸ " : "  ") + m, color: i === menuIdx ? "#9affd9" : "#3f9c80" }));
  } else if (flash) {
    lcdRows = [{ text: `${unitName}   CH${chan}`, color: "#7be8c8" }, { text: "" }, { text: "  " + flash, color: "#9affd9" }];
  } else {
    lcdRows = [
      { text: `${unitName}  CH${chan}      OUTPUT ${outputOn ? "ON" : "OFF"}`, color: outputOn ? "#7be8c8" : "#4fbf9c" },
      { text: `${fpV.toFixed(3)} V   ${fpI.toFixed(3)} A`, big: true, color: "#9affd9" },
      { text: `${fpP.toFixed(2)} W   ${outputOn ? "CV" : "OFF"}   Lim ${currSet.toFixed(1)}A`, color: "#4fbf9c" },
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
            <span className="font-mono text-[11px] text-faint">{unitName} · E4360A-class · soft control</span>
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
                  <span className="h-2 w-2 rounded-full" style={{ background: outputOn ? "#2dd4ee" : "#2c3543", boxShadow: outputOn ? "0 0 7px #2dd4ee" : "none" }} />
                  <span className="w-[34px] font-mono text-[9px] text-faint">OUT</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-green" style={{ boxShadow: "0 0 6px #34d39988" }} />
                  <span className="w-[34px] font-mono text-[9px] text-faint">LINE</span>
                </div>
              </div>
              <div className="text-center font-mono text-[8px] tracking-wider text-[#3a4456]">1200 W<br />MODULAR<br />SAS</div>
            </div>

            <div className="led-lcd flex min-h-[104px] min-w-[240px] flex-1 flex-col justify-center overflow-hidden rounded-lg border border-[#11352a] px-[18px] py-3.5" style={{ background: "#06120e", boxShadow: "inset 0 0 24px #00000080, inset 0 0 60px #0aff9e10" }}>
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
                    color: fn === "error" ? "#fbbf24" : ((fn === "menu" && mode === "menu") || (fn === "meter" && mode === "meter")) ? "#fff" : "#cfd6e2",
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
                { label: "On/Off", fn: "onoff", active: outputOn },
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
          Press <b className="text-[#cfd6e2]">Voltage</b> or <b className="text-[#cfd6e2]">Current</b>, type a value on the keypad, then <b className="text-[#cfd6e2]">Enter</b> · <b className="text-[#cfd6e2]">Menu</b> + nav ▲▼ + <b className="text-[#cfd6e2]">Sel</b> · <b className="text-[#cfd6e2]">Meter</b> for live readout
        </div>
      </div>
    </div>
  );
}
