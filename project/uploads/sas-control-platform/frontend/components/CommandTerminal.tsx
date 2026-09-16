"use client";

/*
  Guided command terminal.

  A terminal *metaphor* over a closed vocabulary — not a shell. The operator
  types plain-language commands ("open", "close", "read current measurements")
  which resolve to the same validated command templates the rest of the UI
  uses. There is no passthrough: anything not in the registry is rejected
  before it reaches the gateway, so an unfamiliar operator cannot improvise a
  command or discover raw SCPI here.

  Novice affordances:
    * clickable command chips and `help` — no need to memorise anything
    * inline completion hint as you type, Tab to accept
    * ↑/↓ recalls previous commands
    * every response states the plain-language effect, the template dispatched
      and the correlation id, so the operator learns the mapping over time

  TERMINOLOGY NOTE: in instrument and contactor language "open" means
  open-circuit, i.e. output OFF. This registry follows the operator-facing
  convention requested for this platform, where `open` ENABLES output. The
  echo always spells the effect out ("output ON — array energised") so the two
  readings can never be confused. If your lab uses the electrical convention,
  swap the `aliases` between `open` and `close` below — nothing else changes.
*/

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Terminal as TerminalIcon } from "lucide-react";
import { Panel, PanelHeader, Badge } from "@/components/ui/kit";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import {
  useDeviceState,
  useMeta,
  useRole,
  useSafeShutdown,
  useSendCommand,
  useSetOutput,
} from "@/lib/hooks";

type LineKind = "cmd" | "ok" | "err" | "warn" | "info";
interface Line {
  kind: LineKind;
  text: string;
}

type Action =
  | { sort: "output"; enabled: boolean }
  | { sort: "template"; templateId: string; needsNumber?: "voltage_v" | "current_a" }
  | { sort: "shutdown" }
  | { sort: "local"; op: "help" | "clear" | "status" };

interface Command {
  /** Canonical name shown in help and chips. */
  name: string;
  /** Accepted spellings, longest-match first at parse time. */
  aliases: string[];
  summary: string;
  /** Plain-language effect, echoed on dispatch. */
  effect?: string;
  hazardous?: boolean;
  /** Requires typing a phrase to confirm. */
  phrase?: string;
  usage?: string;
  action: Action;
}

const COMMANDS: Command[] = [
  {
    name: "open",
    aliases: ["open", "on", "enable", "enable output", "output on"],
    summary: "Enable the output — energises the simulated array",
    effect: "output ON — array energised at the programmed setpoint",
    hazardous: true,
    action: { sort: "output", enabled: true },
  },
  {
    name: "close",
    aliases: ["close", "off", "disable", "disable output", "output off"],
    summary: "Disable the output — de-energises the array",
    effect: "output OFF — array de-energised",
    action: { sort: "output", enabled: false },
  },
  {
    name: "read",
    aliases: ["read current measurements", "read measurements", "read", "measure", "meas"],
    summary: "Read voltage, current and power now",
    action: { sort: "template", templateId: "read_measurements" },
  },
  {
    name: "status",
    aliases: ["status", "state"],
    summary: "Show the cached device status without querying",
    action: { sort: "local", op: "status" },
  },
  {
    name: "identify",
    aliases: ["identify", "id", "whoami"],
    summary: "Ask the instrument to identify itself",
    action: { sort: "template", templateId: "identify" },
  },
  {
    name: "set voltage",
    aliases: ["set voltage", "voltage", "volt", "v"],
    summary: "Set the programmed output voltage",
    usage: "set voltage 28.0",
    hazardous: true,
    action: { sort: "template", templateId: "set_voltage", needsNumber: "voltage_v" },
  },
  {
    name: "set current",
    aliases: ["set current limit", "set current", "current", "curr", "i"],
    summary: "Set the programmed current limit",
    usage: "set current 4.5",
    hazardous: true,
    action: { sort: "template", templateId: "set_current_limit", needsNumber: "current_a" },
  },
  {
    name: "shutdown",
    aliases: ["shutdown", "safe shutdown", "stop"],
    summary: "Disable output and bring the unit to a safe state",
    effect: "safe shutdown — output disabled, unit to standby",
    hazardous: true,
    phrase: "SHUTDOWN",
    action: { sort: "shutdown" },
  },
  {
    name: "help",
    aliases: ["help", "?", "commands"],
    summary: "List every command this terminal accepts",
    action: { sort: "local", op: "help" },
  },
  {
    name: "clear",
    aliases: ["clear", "cls"],
    summary: "Clear the transcript",
    action: { sort: "local", op: "clear" },
  },
];

/** All aliases, longest first, so "read current measurements" wins over "read". */
const ALIAS_INDEX: { alias: string; cmd: Command }[] = COMMANDS.flatMap((cmd) =>
  cmd.aliases.map((alias) => ({ alias, cmd }))
).sort((a, b) => b.alias.length - a.alias.length);

const LINE_COLOR: Record<LineKind, string> = {
  cmd: "var(--color-active)",
  ok: "var(--color-output)",
  err: "var(--color-alarm)",
  warn: "var(--color-warning)",
  info: "var(--color-ink-dim)",
};

function resolve(raw: string): { cmd: Command; rest: string } | null {
  const input = raw.trim().toLowerCase().replace(/\s+/g, " ");
  for (const { alias, cmd } of ALIAS_INDEX) {
    if (input === alias) return { cmd, rest: "" };
    if (input.startsWith(alias + " ")) return { cmd, rest: input.slice(alias.length + 1).trim() };
  }
  return null;
}

export function CommandTerminal({
  deviceId,
  deviceName,
}: {
  deviceId: string;
  deviceName: string;
}) {
  const state = useDeviceState(deviceId);
  const meta = useMeta();
  const role = useRole();
  const setOutput = useSetOutput(deviceId);
  const sendCommand = useSendCommand(deviceId);
  const safeShutdown = useSafeShutdown(deviceId);

  const readOnly = role === "observer";
  const maxV = meta.data?.soft_limits.max_voltage_v ?? 130;
  const maxA = meta.data?.soft_limits.max_current_a ?? 20;

  const [lines, setLines] = useState<Line[]>([
    { kind: "info", text: `Connected to ${deviceName}. Type help to list commands.` },
  ]);
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [histIdx, setHistIdx] = useState<number | null>(null);
  const [pending, setPending] = useState<{ cmd: Command; value?: number } | null>(null);

  const logRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const push = useCallback((kind: LineKind, text: string) => {
    setLines((l) => [...l, { kind, text }]);
  }, []);

  // keep the transcript pinned to the newest line
  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines]);

  /** Inline completion for the current partial input. */
  const hint = useMemo(() => {
    const t = input.trim().toLowerCase();
    if (!t) return "";
    const match = ALIAS_INDEX.filter((a) => a.alias.startsWith(t)).sort(
      (a, b) => a.alias.length - b.alias.length
    )[0];
    if (!match || match.alias === t) return "";
    return match.alias.slice(t.length);
  }, [input]);

  function dispatch(cmd: Command, value?: number) {
    const a = cmd.action;

    if (a.sort === "output") {
      setOutput.mutate(
        { enabled: a.enabled, confirmed: true },
        {
          onSuccess: (r) => {
            push("ok", `${cmd.effect ?? cmd.name} · ${r.status} · corr ${r.request_id}`);
          },
          onError: (e) => push("err", (e as Error).message),
        }
      );
      return;
    }

    if (a.sort === "shutdown") {
      safeShutdown.mutate(undefined, {
        onSuccess: (r) => push("ok", `${cmd.effect} · ${r.status} · corr ${r.request_id}`),
        onError: (e) => push("err", (e as Error).message),
      });
      return;
    }

    if (a.sort === "template") {
      const params: Record<string, number> = {};
      if (a.needsNumber && value !== undefined) params[a.needsNumber] = value;
      sendCommand.mutate(
        { template_id: a.templateId, params, confirmed: true },
        {
          onSuccess: (r) => {
            const detail = r.scpi_response ? `→ ${r.scpi_response}` : r.status;
            push("ok", `${a.templateId} ${detail} · ${r.latency_ms} ms · corr ${r.request_id}`);
            if (!r.readback_verified && r.status === "completed") {
              push("warn", "readback not verified — value sent but not confirmed by the instrument");
            }
          },
          onError: (e) => push("err", (e as Error).message),
        }
      );
      return;
    }

    // local, non-dispatching commands
    if (a.op === "help") {
      push("info", "Available commands — arguments in angle brackets:");
      for (const c of COMMANDS) {
        const label = (c.usage ?? c.name).padEnd(22, " ");
        push("info", `  ${label}${c.summary}${c.hazardous ? "   [confirms]" : ""}`);
      }
      return;
    }
    if (a.op === "clear") {
      setLines([{ kind: "info", text: `Transcript cleared. Connected to ${deviceName}.` }]);
      return;
    }
    const s = state.data;
    if (!s) {
      push("warn", "no cached state yet — try read");
      return;
    }
    push(
      "ok",
      `output ${s.output_enabled ? "ON" : "OFF"} · ${s.voltage_v.toFixed(3)} V · ${s.current_a.toFixed(3)} A · ${s.power_w.toFixed(2)} W`
    );
    push(
      "info",
      `state ${s.device_state} · comms ${s.comm_health} · alarm ${s.alarm_state ?? "none"} · ${s.simulation ? "simulation" : "hardware"}`
    );
  }

  function submit(rawInput: string) {
    const raw = rawInput.trim();
    if (!raw) return;

    push("cmd", `> ${raw}`);
    setHistory((h) => [...h, raw]);
    setHistIdx(null);
    setInput("");

    const match = resolve(raw);
    if (!match) {
      push("err", `unknown command: "${raw}"`);
      push("info", "this terminal only accepts the listed commands — type help to see them");
      return;
    }
    const { cmd, rest } = match;

    if (readOnly && cmd.action.sort !== "local") {
      push("err", "your role is read-only — switch to operator or above to send commands");
      return;
    }

    // numeric argument handling
    let value: number | undefined;
    if (cmd.action.sort === "template" && cmd.action.needsNumber) {
      const parsed = Number.parseFloat(rest);
      if (!Number.isFinite(parsed)) {
        push("err", `${cmd.name} needs a number — e.g. ${cmd.usage}`);
        return;
      }
      const isVolt = cmd.action.needsNumber === "voltage_v";
      const limit = isVolt ? maxV : maxA;
      if (parsed < 0 || parsed > limit) {
        push("err", `${parsed} is outside the soft limit (0 – ${limit} ${isVolt ? "V" : "A"})`);
        return;
      }
      value = parsed;
    }

    if (cmd.hazardous) {
      setPending({ cmd, value });
      return;
    }
    dispatch(cmd, value);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      submit(input);
      return;
    }
    if (e.key === "Tab" && hint) {
      e.preventDefault();
      setInput((i) => i.trim() + hint);
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (history.length === 0) return;
      const next = histIdx === null ? history.length - 1 : Math.max(0, histIdx - 1);
      setHistIdx(next);
      setInput(history[next]);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (histIdx === null) return;
      const next = histIdx + 1;
      if (next >= history.length) {
        setHistIdx(null);
        setInput("");
      } else {
        setHistIdx(next);
        setInput(history[next]);
      }
    }
  }

  const busy = setOutput.isPending || sendCommand.isPending || safeShutdown.isPending;

  return (
    <Panel>
      <PanelHeader
        eyebrow="Guided console"
        title="Command terminal"
        actions={
          <div className="flex items-center gap-2">
            {readOnly ? <Badge color="var(--color-offline)">read only</Badge> : null}
            <span className="flex items-center gap-1 text-xs text-[var(--color-ink-faint)]">
              <TerminalIcon size={12} /> closed vocabulary
            </span>
          </div>
        }
      />

      {/* quick-pick chips so nothing has to be memorised */}
      <div className="flex flex-wrap gap-1.5 border-b border-[var(--color-hairline)] px-3 py-2.5">
        {COMMANDS.filter((c) => c.action.sort !== "local" || c.name === "help").map((c) => (
          <button
            key={c.name}
            onClick={() => {
              if (c.usage) {
                setInput(c.usage);
                inputRef.current?.focus();
              } else {
                submit(c.name);
              }
            }}
            title={c.summary}
            className="rounded-md border px-2 py-1 text-[11px] font-medium transition-colors"
            style={{
              borderColor: c.hazardous
                ? "color-mix(in srgb, var(--color-warning) 35%, transparent)"
                : "var(--color-hairline)",
              color: c.hazardous ? "var(--color-warning)" : "var(--color-ink-dim)",
              background: "var(--color-base)",
            }}
          >
            {c.usage ?? c.name}
          </button>
        ))}
      </div>

      {/* transcript */}
      <div
        ref={logRef}
        className="readout h-64 overflow-y-auto px-3 py-2.5 text-xs leading-relaxed"
        style={{ background: "var(--color-base)" }}
      >
        {lines.map((l, i) => (
          <div key={i} className="whitespace-pre-wrap" style={{ color: LINE_COLOR[l.kind] }}>
            {l.text}
          </div>
        ))}
        {busy ? <div style={{ color: "var(--color-ink-faint)" }}>working…</div> : null}
      </div>

      {/* prompt */}
      <div className="flex items-center gap-2 border-t border-[var(--color-hairline)] px-3 py-2.5">
        <span className="readout text-sm" style={{ color: "var(--color-active)" }}>
          &gt;
        </span>
        <div className="relative flex-1">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={readOnly ? "read-only role" : "type a command, or click one above"}
            spellCheck={false}
            autoComplete="off"
            className="readout h-9 w-full rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] px-3 text-sm text-[var(--color-ink)] focus-visible:border-[var(--color-active)]"
          />
          {/* ghost completion */}
          {hint ? (
            <span
              aria-hidden
              className="readout pointer-events-none absolute left-3 top-0 flex h-9 items-center text-sm"
              style={{ color: "transparent" }}
            >
              {input.trim()}
              <span style={{ color: "var(--color-ink-faint)" }}>{hint}</span>
            </span>
          ) : null}
        </div>
        <span className="text-[10px] text-[var(--color-ink-faint)]">
          {hint ? "Tab to complete" : "↑ history"}
        </span>
      </div>

      <ConfirmDialog
        open={!!pending}
        title={`Confirm: ${pending?.cmd.name ?? ""}`}
        destructive={pending?.cmd.action.sort === "shutdown"}
        requirePhrase={pending?.cmd.phrase}
        body={
          <span>
            {pending?.cmd.effect ?? pending?.cmd.summary}
            {pending?.value !== undefined ? (
              <>
                {" — value "}
                <span className="readout text-[var(--color-ink)]">{pending.value}</span>
              </>
            ) : null}
            . Dispatched to{" "}
            <span className="readout text-[var(--color-ink)]">{deviceName}</span> as a validated
            command and recorded in the audit log.
          </span>
        }
        confirmLabel={`Send ${pending?.cmd.name ?? ""}`}
        onConfirm={() => {
          if (pending) dispatch(pending.cmd, pending.value);
          setPending(null);
        }}
        onCancel={() => {
          push("info", "cancelled — nothing was sent");
          setPending(null);
        }}
      />
    </Panel>
  );
}
