import type { TerminalCommand } from "./types";

// Mirrors backend/app/data.py TERM_CMDS — closed vocabulary, no passthrough.
// "open" energises the output here; every echo spells out the effect so it
// can't be misread as open-circuit.
export const TERM_CMDS: TerminalCommand[] = [
  { name: "open", aliases: ["open", "on", "enable", "enable output", "output on"], summary: "Enable the output — energises the array", effect: "output ON — array energised", hazardous: true, act: "on" },
  { name: "close", aliases: ["close", "off", "disable", "disable output", "output off"], summary: "Disable the output — de-energises the array", effect: "output OFF — array de-energised", hazardous: false, act: "off" },
  { name: "read", aliases: ["read current measurements", "read measurements", "read", "measure", "meas"], summary: "Read voltage, current and power now", hazardous: false, act: "read" },
  { name: "status", aliases: ["status", "state"], summary: "Show cached device status without querying", hazardous: false, act: "status" },
  { name: "identify", aliases: ["identify", "id", "whoami"], summary: "Ask the instrument to identify itself", hazardous: false, act: "idn" },
  { name: "set voltage", aliases: ["set voltage", "voltage", "volt", "v"], summary: "Set the programmed output voltage", usage: "set voltage 28.0", hazardous: true, act: "setv", unit: "V", max: 32 },
  { name: "set current", aliases: ["set current limit", "set current", "current", "curr", "i"], summary: "Set the programmed current limit", usage: "set current 4.5", hazardous: true, act: "seti", unit: "A", max: 6 },
  { name: "shutdown", aliases: ["shutdown", "safe shutdown", "stop"], summary: "Disable output and bring the unit to a safe state", effect: "safe shutdown — output disabled, unit to standby", hazardous: true, act: "shutdown" },
  { name: "help", aliases: ["help", "?", "commands"], summary: "List every command this terminal accepts", hazardous: false, act: "help" },
  { name: "clear", aliases: ["clear", "cls"], summary: "Clear the transcript", hazardous: false, act: "clear" },
];

const aliasIndex = TERM_CMDS.flatMap((c) => c.aliases.map((a) => ({ a, c }))).sort((x, y) => y.a.length - x.a.length);

export function resolveCommand(raw: string): { cmd: TerminalCommand; rest: string } | null {
  const input = raw.trim().toLowerCase().replace(/\s+/g, " ");
  for (const { a, c } of aliasIndex) {
    if (input === a) return { cmd: c, rest: "" };
    if (input.startsWith(a + " ")) return { cmd: c, rest: input.slice(a.length + 1).trim() };
  }
  return null;
}

export function hintFor(input: string): string {
  const t = input.trim().toLowerCase();
  if (!t) return "";
  const hits = aliasIndex.filter((x) => x.a.startsWith(t)).sort((x, y) => x.a.length - y.a.length);
  if (!hits.length || hits[0].a === t) return "";
  return hits[0].a.slice(t.length);
}
