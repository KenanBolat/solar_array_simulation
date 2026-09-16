import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Map a device_state string to a status token color (CSS var name). */
export function stateColor(state: string | undefined): string {
  switch (state) {
    case "online":
      return "var(--color-online)";
    case "output_enabled":
      return "var(--color-output)";
    case "running_scenario":
      return "var(--color-scenario)";
    case "armed":
      return "var(--color-active)";
    case "warning":
      return "var(--color-warning)";
    case "alarm":
      return "var(--color-alarm)";
    case "offline":
    case "unknown":
    default:
      return "var(--color-offline)";
  }
}

export function stateLabel(state: string | undefined): string {
  switch (state) {
    case "output_enabled":
      return "Output On";
    case "running_scenario":
      return "Running";
    case "online":
      return "Online";
    case "armed":
      return "Armed";
    case "warning":
      return "Warning";
    case "alarm":
      return "Alarm";
    case "offline":
      return "Offline";
    default:
      return "Unknown";
  }
}

export function fmt(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toISOString().replace("T", " ").replace("Z", "").slice(0, 19) + "Z";
}

export function relTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
