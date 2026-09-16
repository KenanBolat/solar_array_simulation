import * as React from "react";
import { cn } from "@/lib/utils";

export function Panel({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("panel", className)} {...props} />;
}

export function PanelHeader({
  title,
  eyebrow,
  actions,
}: {
  title: React.ReactNode;
  eyebrow?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="panel-header">
      <div className="flex flex-col gap-0.5">
        {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
        <span className="text-sm font-semibold text-[var(--color-ink)]">{title}</span>
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function Badge({
  children,
  color = "var(--color-offline)",
  className,
}: {
  children: React.ReactNode;
  color?: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium",
        className
      )}
      style={{
        color,
        borderColor: `color-mix(in srgb, ${color} 35%, transparent)`,
        background: `color-mix(in srgb, ${color} 12%, transparent)`,
      }}
    >
      {children}
    </span>
  );
}

export function StatusDot({ color, pulse }: { color: string; pulse?: boolean }) {
  return (
    <span
      className={cn("status-dot inline-block", pulse && "status-pulse")}
      style={{ color, background: color }}
    />
  );
}

export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="eyebrow">{label}</span>
      {children}
      {hint ? <span className="text-xs text-[var(--color-ink-faint)]">{hint}</span> : null}
    </label>
  );
}

export function NumberInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type="number"
      {...props}
      className={cn(
        "readout h-9 rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] px-3 text-sm text-[var(--color-ink)] focus-visible:border-[var(--color-active)]",
        props.className
      )}
    />
  );
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={cn(
        "h-9 rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] px-3 text-sm text-[var(--color-ink)] focus-visible:border-[var(--color-active)]",
        props.className
      )}
    />
  );
}
