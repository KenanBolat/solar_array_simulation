import type { ReactNode } from "react";

export function Panel({ children, className = "", title }: { children: ReactNode; className?: string; title?: string }) {
  return (
    <div className={`rounded-[10px] border border-line bg-panel ${className}`}>
      {title && (
        <div className="border-b border-line px-3.5 py-2.5 text-[12px] font-semibold">{title}</div>
      )}
      {children}
    </div>
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="mb-2.5 text-[11px] uppercase tracking-wider text-muted">{children}</div>;
}

export function StatCard({
  label, value, unit, color = "#e6eaf2",
}: { label: string; value: string | number; unit?: string; color?: string }) {
  return (
    <div className="rounded-[9px] border border-line bg-panel px-[15px] py-[13px]">
      <div className="mb-1.5 text-[10.5px] uppercase tracking-wider text-muted">{label}</div>
      <div className="font-mono text-[26px] font-semibold" style={{ color }}>
        {value}
        {unit && <span className="text-[13px] text-faint">{unit}</span>}
      </div>
    </div>
  );
}

export function Chip({
  label, active, onClick, hazardous,
}: { label: string; active?: boolean; onClick?: () => void; hazardous?: boolean }) {
  return (
    <div
      onClick={onClick}
      className="cursor-pointer whitespace-nowrap rounded-md px-3 py-1.5 text-[11.5px] font-semibold"
      style={{
        color: active ? "#fff" : hazardous ? "#fbbf24" : "#8a95a8",
        background: active ? "#2dd4ee1f" : "transparent",
        border: `1px solid ${active ? "#2dd4ee66" : hazardous ? "#fbbf2455" : "#232a36"}`,
      }}
    >
      {label}
    </div>
  );
}

export function StatusDot({ color, pulse }: { color: string; pulse?: boolean }) {
  return (
    <span
      className={`inline-block h-[9px] w-[9px] flex-none rounded-full ${pulse ? "animate-scpulse" : ""}`}
      style={{ background: color, boxShadow: `0 0 8px ${color}66` }}
    />
  );
}

export function Btn({
  children, onClick, variant = "default", className = "", disabled,
}: {
  children: ReactNode; onClick?: () => void; variant?: "default" | "primary" | "danger" | "success"; className?: string; disabled?: boolean;
}) {
  const styles: Record<string, string> = {
    default: "border border-line2 bg-panel2 text-ink",
    primary: "border border-cyan/40 bg-cyan/[0.08] text-cyan",
    danger: "border border-red/60 bg-red/10 text-red",
    success: "border-none bg-green text-[#04130c]",
  };
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`rounded-md px-3.5 py-2 text-[12px] font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

export const STATUS_COLOR: Record<string, string> = {
  faint: "#5c6678",
  amber: "#fbbf24",
  cyan: "#2dd4ee",
  green: "#34d399",
};

export const SEV_COLOR: Record<string, string> = {
  warning: "#fbbf24",
  critical: "#f87171",
  info: "#3b82f6",
};

export const RUN_COLOR: Record<string, string> = {
  Running: "#2dd4ee",
  Completed: "#34d399",
  Aborted: "#fbbf24",
  Failed: "#f87171",
  Queued: "#8a95a8",
};

export const HIST_COLOR: Record<string, string> = {
  OK: "#34d399",
  WARN: "#fbbf24",
  ERR: "#f87171",
};

export function Sev({ sev }: { sev: string }) {
  const c = SEV_COLOR[sev] || "#8a95a8";
  return (
    <span
      className="rounded font-mono text-[9.5px] font-semibold tracking-wider"
      style={{ color: c, border: `1px solid ${c}55`, padding: "2px 6px" }}
    >
      {sev.toUpperCase()}
    </span>
  );
}
