import * as React from "react";

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex items-end justify-between border-b border-[var(--color-hairline)] px-6 py-4">
      <div>
        <h1 className="text-lg font-semibold text-[var(--color-ink)]">{title}</h1>
        {subtitle ? (
          <p className="mt-0.5 text-sm text-[var(--color-ink-dim)]">{subtitle}</p>
        ) : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function StatCard({
  label,
  value,
  unit,
  accent = "var(--color-ink)",
}: {
  label: string;
  value: React.ReactNode;
  unit?: string;
  accent?: string;
}) {
  return (
    <div className="panel px-4 py-3">
      <div className="eyebrow">{label}</div>
      <div className="mt-1 flex items-baseline gap-1">
        <span className="readout text-2xl font-semibold" style={{ color: accent }}>
          {value}
        </span>
        {unit ? <span className="text-xs text-[var(--color-ink-faint)]">{unit}</span> : null}
      </div>
    </div>
  );
}
