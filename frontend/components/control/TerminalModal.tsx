"use client";
import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { useUi } from "@/lib/ui-context";
import { TERM_CMDS, resolveCommand, hintFor } from "@/lib/terminal-commands";

interface Line { k: "cmd" | "ok" | "err" | "warn" | "info"; t: string }

const LINE_COLOR: Record<Line["k"], string> = {
  cmd: "#2dd4ee", ok: "#34d399", err: "#f87171", warn: "#fbbf24", info: "#8a95a8",
};

export function TerminalModal({ unitName, onClose, onChanged }: { unitName: string; onClose: () => void; onChanged: () => void }) {
  const { ask } = useUi();
  const [lines, setLines] = useState<Line[]>([{ k: "info", t: `Connected to ${unitName}. Type help to list commands.` }]);
  const [input, setInput] = useState("");
  const [hist, setHist] = useState<string[]>([]);
  const [histIdx, setHistIdx] = useState<number | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  const push = (k: Line["k"], t: string) => {
    setLines((ls) => [...ls, { k, t }]);
    requestAnimationFrame(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; });
  };

  const runResolved = async (act: string, label: string, value?: number) => {
    if (act === "help") {
      push("info", "Available commands — arguments in angle brackets:");
      TERM_CMDS.forEach((x) => {
        const lbl = x.usage || x.name;
        const pad = lbl + " ".repeat(Math.max(1, 22 - lbl.length));
        push("info", `  ${pad}${x.summary}${x.hazardous ? "   [confirms]" : ""}`);
      });
      return;
    }
    if (act === "clear") {
      setLines([{ k: "info", t: `Transcript cleared. Connected to ${unitName}.` }]);
      return;
    }
    try {
      const res = await api.terminalExecute(unitName, act, label, value);
      push("ok", res.line);
      onChanged();
    } catch (e) {
      push("err", e instanceof Error ? e.message : "command failed");
    }
  };

  const submit = (raw: string) => {
    const trimmed = raw.trim();
    if (!trimmed) return;
    push("cmd", "> " + trimmed);
    setHist((h) => [...h, trimmed]);
    setHistIdx(null);
    setInput("");
    const m = resolveCommand(trimmed);
    if (!m) {
      push("err", `unknown command: "${trimmed}"`);
      push("info", "this terminal only accepts the listed commands — type help to see them");
      return;
    }
    const { cmd, rest } = m;
    let value: number | undefined;
    if (cmd.act === "setv" || cmd.act === "seti") {
      const p = parseFloat(rest);
      if (!isFinite(p)) { push("err", `${cmd.name} needs a number — e.g. ${cmd.usage}`); return; }
      if (p < 0 || p > (cmd.max ?? Infinity)) { push("err", `${p} is outside the soft limit (0 – ${cmd.max} ${cmd.unit})`); return; }
      value = p;
    }
    if (cmd.hazardous) {
      ask({
        title: `Confirm: ${cmd.name}`,
        message: `${cmd.effect || cmd.summary}${value !== undefined ? ` — value ${value}` : ""}. Sent to ${unitName} as SCPI, confirmed with *OPC? / SYST:ERR? / readback, and recorded in the audit log.`,
        confirmLabel: `Send ${cmd.name}`,
        danger: cmd.act === "shutdown",
        onConfirm: () => runResolved(cmd.act, cmd.name, value),
      });
      return;
    }
    runResolved(cmd.act, cmd.name, value);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") { submit(input); return; }
    if (e.key === "Tab") {
      const h = hintFor(input);
      if (h) { e.preventDefault(); setInput((s) => s.trim() + h); }
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!hist.length) return;
      const n = histIdx === null ? hist.length - 1 : Math.max(0, histIdx - 1);
      setHistIdx(n); setInput(hist[n]);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (histIdx === null) return;
      const n = histIdx + 1;
      if (n >= hist.length) { setHistIdx(null); setInput(""); }
      else { setHistIdx(n); setInput(hist[n]); }
    }
  };

  const hint = hintFor(input);

  return (
    <div data-testid="terminal-modal" className="fixed inset-0 z-[55] flex items-center justify-center bg-[#05070ad8] p-7">
      <div className="w-[760px] max-w-full overflow-hidden rounded-xl border border-line2 bg-panel shadow-[0_30px_80px_rgba(0,0,0,0.6)]">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div>
            <div className="text-[9.5px] font-semibold uppercase tracking-[0.12em] text-faint">Guided console</div>
            <div className="text-[13px] font-semibold">Command Terminal · {unitName}</div>
          </div>
          <div className="flex items-center gap-2.5">
            <span className="font-mono text-[10px] text-faint">closed vocabulary → real SCPI · no passthrough</span>
            <button
              onClick={onClose}
              className="flex h-7 w-7 items-center justify-center rounded-md border border-line2 bg-panel2 text-[15px] text-ink"
            >
              ✕
            </button>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5 border-b border-line px-3.5 py-2.5">
          {TERM_CMDS.filter((c) => c.act !== "clear").map((c) => (
            <div
              key={c.name}
              title={c.summary}
              onClick={() => (c.usage ? setInput(c.usage) : submit(c.name))}
              className="cursor-pointer rounded-md px-2.5 py-1 font-mono text-[11px] font-medium"
              style={{
                background: "#0e1117",
                border: `1px solid ${c.hazardous ? "#fbbf2455" : "#232a36"}`,
                color: c.hazardous ? "#fbbf24" : "#8a95a8",
              }}
            >
              {c.usage || c.name}
            </div>
          ))}
        </div>
        <div ref={logRef} className="h-[260px] overflow-y-auto bg-bg px-3.5 py-3">
          {lines.map((l, idx) => (
            <div key={idx} className="whitespace-pre-wrap font-mono text-[11.5px] leading-relaxed" style={{ color: LINE_COLOR[l.k] }}>
              {l.t}
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2.5 border-t border-line px-3.5 py-2.5">
          <span className="font-mono text-[14px] text-cyan">&gt;</span>
          <div className="relative flex-1">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="type a command, or click one above"
              spellCheck={false}
              autoComplete="off"
              className="h-[34px] w-full rounded-md border border-line2 bg-bg px-2.5 font-mono text-[13px] text-ink outline-none"
            />
            <span className="pointer-events-none absolute left-2.5 top-0 flex h-[34px] items-center font-mono text-[13px] text-transparent">
              {input}
              <span className="text-faint">{hint}</span>
            </span>
          </div>
          <span className="w-[78px] text-right text-[10px] text-faint">{hint ? "Tab to complete" : "↑ history"}</span>
        </div>
      </div>
    </div>
  );
}
