"use client";

/*
  Virtual soft front panel for a controlled SAS unit.

  This is a generic instrument-style console — LCD readout, soft keys, a nav
  cluster and a numeric keypad — not a reproduction of any vendor's front
  panel. Every write goes through the same validated command templates the rest
  of the UI uses (`set_voltage`, `set_current_limit`, `output_on`/`output_off`),
  so entries here are audited and correlation-tracked identically to the
  software controls.

  Interaction model:
    Voltage / Current  -> enter numeric-entry mode for that field
    digits . E +/- del -> edit the entry buffer
    Enter              -> clamp to soft limits and dispatch the command
    Menu + nav + Sel   -> walk a short menu of the same actions
    Meter              -> live readout
*/

import { useCallback, useEffect, useMemo, useState } from "react";
import { Panel, PanelHeader, Badge } from "@/components/ui/kit";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useDeviceState, useMeta, useRole, useSendCommand, useSetOutput } from "@/lib/hooks";

type Mode = "meter" | "entry" | "menu";
type EntryField = "VOLTAGE" | "CURRENT";
type LcdRow = { text: string; big?: boolean; dim?: boolean };

const MENU_ITEMS = [
  "Output On/Off",
  "Set Voltage",
  "Set Current Limit",
  "Refresh Measurements",
  "Identify Device",
] as const;

const KEYS: { label: string; key: string }[] = [
  { label: "7", key: "7" },
  { label: "8", key: "8" },
  { label: "9", key: "9" },
  { label: "▲", key: "up" },
  { label: "4", key: "4" },
  { label: "5", key: "5" },
  { label: "6", key: "6" },
  { label: "▼", key: "down" },
  { label: "1", key: "1" },
  { label: "2", key: "2" },
  { label: "3", key: "3" },
  { label: "E", key: "E" },
  { label: "0", key: "0" },
  { label: ".", key: "." },
  { label: "+/−", key: "sign" },
  { label: "⌫", key: "back" },
];

export function FrontPanel({ deviceId, deviceName }: { deviceId: string; deviceName: string }) {
  const state = useDeviceState(deviceId);
  const meta = useMeta();
  const role = useRole();
  const setOutput = useSetOutput(deviceId);
  const sendCommand = useSendCommand(deviceId);

  const [mode, setMode] = useState<Mode>("meter");
  const [field, setField] = useState<EntryField>("VOLTAGE");
  const [buffer, setBuffer] = useState("");
  const [menuIndex, setMenuIndex] = useState(0);
  const [flash, setFlash] = useState<string | null>(null);
  const [pendingOutput, setPendingOutput] = useState(false);

  const readOnly = role === "observer";
  const maxV = meta.data?.soft_limits.max_voltage_v ?? 130;
  const maxA = meta.data?.soft_limits.max_current_a ?? 20;

  const showFlash = useCallback((msg: string) => setFlash(msg), []);

  useEffect(() => {
    if (!flash) return;
    const t = setTimeout(() => setFlash(null), 1600);
    return () => clearTimeout(t);
  }, [flash]);

  const s = state.data;
  const outputOn = !!s?.output_enabled;

  function guard(): boolean {
    if (readOnly) {
      showFlash("OBSERVER ROLE — READ ONLY");
      return false;
    }
    return true;
  }

  function pressDigit(k: string) {
    if (mode !== "entry") {
      showFlash("PRESS VOLTAGE OR CURRENT FIRST");
      return;
    }
    setBuffer((b) => {
      if (/^[0-9]$/.test(k)) return b + k;
      if (k === ".") return b.includes(".") ? b : (b === "" || b === "-" ? b + "0." : b + ".");
      if (k === "E") return b === "" || b.includes("E") ? b : b + "E";
      if (k === "sign") return b.startsWith("-") ? b.slice(1) : "-" + b;
      if (k === "back") return b.slice(0, -1);
      return b;
    });
  }

  function commitEntry() {
    if (mode !== "entry") {
      showFlash("NOTHING TO ENTER");
      return;
    }
    if (!guard()) return;
    const parsed = Number.parseFloat(buffer);
    if (!Number.isFinite(parsed)) {
      showFlash("INVALID ENTRY");
      return;
    }
    const isVolt = field === "VOLTAGE";
    const limit = isVolt ? maxV : maxA;
    const clamped = Math.min(Math.max(parsed, 0), limit);
    if (clamped !== parsed) showFlash(`CLAMPED TO SOFT LIMIT ${limit}`);

    sendCommand.mutate(
      {
        template_id: isVolt ? "set_voltage" : "set_current_limit",
        params: isVolt ? { voltage_v: clamped } : { current_a: clamped },
        confirmed: true,
      },
      {
        onSuccess: (r) =>
          showFlash(
            `${isVolt ? "VOLT" : "CURR LIM"} ${clamped} ${isVolt ? "V" : "A"} · ${r.status.toUpperCase()}`
          ),
        onError: (e) => showFlash((e as Error).message.slice(0, 38).toUpperCase()),
      }
    );
    setBuffer("");
    setMode("meter");
  }

  function toggleOutput() {
    if (!guard()) return;
    // Enabling energises the array output — always confirm. Disabling is the
    // safe direction and goes straight through, matching hardware behaviour.
    if (!outputOn) {
      setPendingOutput(true);
      return;
    }
    setOutput.mutate(
      { enabled: false, confirmed: true },
      {
        onSuccess: () => showFlash("OUTPUT DISABLED"),
        onError: (e) => showFlash((e as Error).message.slice(0, 38).toUpperCase()),
      }
    );
  }

  function confirmEnable() {
    setPendingOutput(false);
    setOutput.mutate(
      { enabled: true, confirmed: true },
      {
        onSuccess: () => showFlash("OUTPUT ENABLED"),
        onError: (e) => showFlash((e as Error).message.slice(0, 38).toUpperCase()),
      }
    );
  }

  function runTemplate(templateId: string, label: string) {
    if (!guard()) return;
    sendCommand.mutate(
      { template_id: templateId, params: {}, confirmed: true },
      {
        onSuccess: (r) => showFlash(`${label} · ${(r.scpi_response ?? r.status).slice(0, 26)}`),
        onError: (e) => showFlash((e as Error).message.slice(0, 38).toUpperCase()),
      }
    );
  }

  function softKey(name: string) {
    if (name === "meter") setMode("meter");
    else if (name === "menu") setMode("menu");
    else if (name === "back") {
      setMode("meter");
      setBuffer("");
    } else if (name === "help") showFlash("MENU + NAV + SEL · DIGITS THEN ENTER");
    else if (name === "error") showFlash(s?.alarm_state ? s.alarm_state.toUpperCase() : "NO ERROR  +0");
    else if (name === "channel") showFlash(`${deviceName} · ${s?.device_mode ?? "—"}`);
  }

  function nav(dir: "up" | "down" | "sel") {
    if (mode === "menu") {
      if (dir === "up") setMenuIndex((i) => (i + MENU_ITEMS.length - 1) % MENU_ITEMS.length);
      else if (dir === "down") setMenuIndex((i) => (i + 1) % MENU_ITEMS.length);
      else {
        const item = MENU_ITEMS[menuIndex];
        if (item === "Output On/Off") toggleOutput();
        else if (item === "Set Voltage") {
          setField("VOLTAGE");
          setBuffer("");
          setMode("entry");
        } else if (item === "Set Current Limit") {
          setField("CURRENT");
          setBuffer("");
          setMode("entry");
        } else if (item === "Refresh Measurements") runTemplate("read_measurements", "MEAS");
        else runTemplate("identify", "IDN");
      }
      return;
    }
    if (dir === "sel") {
      setMode("meter");
      return;
    }
    // Outside the menu the steppers nudge the pending entry value.
    if (mode === "entry") {
      const step = dir === "up" ? 0.1 : -0.1;
      const limit = field === "VOLTAGE" ? maxV : maxA;
      const current = Number.parseFloat(buffer);
      const next = Math.min(Math.max((Number.isFinite(current) ? current : 0) + step, 0), limit);
      setBuffer(next.toFixed(2));
    }
  }

  const lcd = useMemo<LcdRow[]>(() => {
    if (mode === "entry") {
      const unit = field === "VOLTAGE" ? "V" : "A";
      const limit = field === "VOLTAGE" ? maxV : maxA;
      return [
        { text: `SET ${field}`, dim: true },
        { text: `> ${buffer}█`, big: true },
        { text: `Range 0 – ${limit} ${unit}   Enter = apply`, dim: true },
      ];
    }
    if (flash) {
      return [
        { text: `${deviceName}`, dim: true },
        { text: "", dim: true },
        { text: `  ${flash}`, big: false },
      ];
    }
    if (mode === "menu") {
      return [
        { text: "MAIN MENU", dim: true },
        ...MENU_ITEMS.map((m, i) => ({
          text: `${i === menuIndex ? "▸ " : "  "}${m}`,
          dim: i !== menuIndex,
        })),
      ];
    }
    if (!s) return [{ text: "READING DEVICE…", dim: true }];
    return [
      {
        text: `${deviceName}     OUTPUT ${outputOn ? "ON" : "OFF"}${s.connected ? "" : "  [OFFLINE]"}`,
        dim: !outputOn,
      },
      { text: `${s.voltage_v.toFixed(3)} V   ${s.current_a.toFixed(3)} A`, big: true },
      {
        text: `${s.power_w.toFixed(2)} W   ${s.device_state.toUpperCase()}   ${s.comm_health.toUpperCase()}`,
        dim: true,
      },
    ];
  }, [mode, field, buffer, flash, menuIndex, s, outputOn, deviceName, maxV, maxA]);

  const keyCls =
    "flex h-9 items-center justify-center rounded-md border border-[var(--color-hairline)] bg-[var(--color-surface-3)] text-sm font-semibold text-[var(--color-ink-dim)] transition-colors hover:border-[var(--color-hairline-strong)] hover:text-[var(--color-ink)] active:bg-[var(--color-surface-2)]";
  const softCls =
    "flex h-8 items-center justify-center rounded-md border border-[var(--color-hairline)] bg-[var(--color-surface-3)] px-2 text-[11px] font-semibold text-[var(--color-ink-dim)] transition-colors hover:border-[var(--color-hairline-strong)] hover:text-[var(--color-ink)]";

  return (
    <Panel>
      <PanelHeader
        eyebrow="Manual control"
        title="Virtual front panel"
        actions={
          <div className="flex items-center gap-2">
            {readOnly ? <Badge color="var(--color-offline)">read only</Badge> : null}
            <Badge color={outputOn ? "var(--color-output)" : "var(--color-offline)"}>
              {outputOn ? "output on" : "output off"}
            </Badge>
          </div>
        }
      />

      <div className="space-y-3 p-3">
        {/* LCD */}
        <div
          className="readout overflow-hidden rounded-md border px-4 py-3"
          style={{
            minHeight: 104,
            borderColor: "#11352a",
            background:
              "repeating-linear-gradient(0deg, rgba(10,255,158,0.03) 0 1px, transparent 1px 3px), #06120e",
            boxShadow: "inset 0 0 24px rgba(0,0,0,0.5)",
          }}
        >
          {lcd.map((row, i) => (
            <div
              key={i}
              className="whitespace-pre"
              style={{
                color: row.dim ? "#4fbf9c" : "#9affd9",
                fontSize: row.big ? 19 : 12,
                fontWeight: row.big ? 600 : 400,
                lineHeight: 1.5,
                textShadow: "0 0 8px rgba(90,242,201,0.35)",
              }}
            >
              {row.text}
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-start gap-3">
          {/* soft keys */}
          <div className="grid grid-cols-2 gap-1.5">
            {[
              ["Meter", "meter"],
              ["Menu", "menu"],
              ["Channel", "channel"],
              ["Back", "back"],
              ["Help", "help"],
              ["Error", "error"],
            ].map(([label, fn]) => (
              <button
                key={fn}
                onClick={() => softKey(fn)}
                className={softCls}
                style={
                  (fn === "meter" && mode === "meter") || (fn === "menu" && mode === "menu")
                    ? { borderColor: "var(--color-active)", color: "var(--color-ink)" }
                    : fn === "error"
                      ? { color: "var(--color-warning)" }
                      : undefined
                }
              >
                {label}
              </button>
            ))}
          </div>

          {/* nav cluster */}
          <div className="flex flex-col items-center gap-1.5">
            <button onClick={() => nav("up")} className={`${keyCls} w-9`}>
              ▲
            </button>
            <div className="flex items-center gap-1.5">
              <button onClick={() => softKey("back")} className={`${keyCls} w-9`}>
                ◄
              </button>
              <button
                onClick={() => nav("sel")}
                className="flex h-9 w-9 items-center justify-center rounded-full border text-[11px] font-bold"
                style={{
                  borderColor: "color-mix(in srgb, var(--color-active) 45%, transparent)",
                  background: "var(--color-surface-3)",
                  color: "var(--color-active)",
                }}
              >
                Sel
              </button>
              <button onClick={() => setMode("menu")} className={`${keyCls} w-9`}>
                ►
              </button>
            </div>
            <button onClick={() => nav("down")} className={`${keyCls} w-9`}>
              ▼
            </button>
          </div>

          {/* function keys */}
          <div className="grid w-[86px] gap-1.5">
            <button
              onClick={toggleOutput}
              disabled={readOnly || setOutput.isPending}
              className="flex h-10 items-center justify-center rounded-md border text-xs font-semibold disabled:opacity-50"
              style={{
                borderColor: outputOn ? "var(--color-alarm)" : "var(--color-output)",
                color: outputOn ? "var(--color-alarm)" : "var(--color-output)",
                background: `color-mix(in srgb, ${outputOn ? "var(--color-alarm)" : "var(--color-output)"} 10%, transparent)`,
              }}
            >
              On/Off
            </button>
            {(
              [
                ["Voltage", "VOLTAGE"],
                ["Current", "CURRENT"],
              ] as const
            ).map(([label, f]) => (
              <button
                key={f}
                onClick={() => {
                  if (!guard()) return;
                  setField(f);
                  setBuffer("");
                  setMode("entry");
                }}
                className="flex h-10 items-center justify-center rounded-md border text-xs font-semibold"
                style={
                  mode === "entry" && field === f
                    ? {
                        borderColor: "var(--color-active)",
                        color: "var(--color-ink)",
                        background: "color-mix(in srgb, var(--color-active) 12%, transparent)",
                      }
                    : {
                        borderColor: "var(--color-hairline)",
                        color: "var(--color-ink-dim)",
                        background: "var(--color-surface-3)",
                      }
                }
              >
                {label}
              </button>
            ))}
          </div>

          {/* keypad + enter */}
          <div className="flex items-stretch gap-1.5">
            <div className="grid grid-cols-4 gap-1.5">
              {KEYS.map((k) => (
                <button
                  key={k.key}
                  onClick={() => {
                    if (k.key === "up" || k.key === "down") nav(k.key);
                    else pressDigit(k.key);
                  }}
                  className={`${keyCls} w-11`}
                >
                  {k.label}
                </button>
              ))}
            </div>
            <button
              onClick={commitEntry}
              disabled={readOnly || sendCommand.isPending}
              className="w-11 rounded-md border text-xs font-bold disabled:opacity-50"
              style={{
                borderColor: "var(--color-active)",
                background: "var(--color-active)",
                color: "#04121a",
                writingMode: "vertical-rl",
                textOrientation: "mixed",
                letterSpacing: "0.08em",
              }}
            >
              Enter
            </button>
          </div>
        </div>

        <p className="text-[11px] text-[var(--color-ink-faint)]">
          Entries are clamped to the configured soft limits and dispatched as validated
          command templates — every keystroke that reaches the device is audited with a
          correlation id, the same as the software controls.
        </p>
      </div>

      {/* Enable-output confirmation — energising always requires an explicit step. */}
      <ConfirmDialog
        open={pendingOutput}
        title="Enable output"
        body={`This energises the simulated array output on ${deviceName} at the programmed setpoint. Physical interlocks are not affected by this action.`}
        confirmLabel="Enable output"
        onConfirm={confirmEnable}
        onCancel={() => setPendingOutput(false)}
      />
    </Panel>
  );
}
