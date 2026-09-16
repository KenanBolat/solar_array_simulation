"use client";

import { useState } from "react";
import { Check } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Panel, PanelHeader, Badge, Button } from "@/components/ui/kit";
import { useAckAlarm, useAlarms, useRole } from "@/lib/hooks";
import { fmtTime } from "@/lib/utils";

function severityColor(sev: string): string {
  switch (sev) {
    case "critical":
    case "alarm":
      return "var(--color-alarm)";
    case "warning":
      return "var(--color-warning)";
    case "info":
      return "var(--color-active)";
    default:
      return "var(--color-offline)";
  }
}

export default function AlarmsPage() {
  const [activeOnly, setActiveOnly] = useState(true);
  const alarms = useAlarms(activeOnly);
  const ack = useAckAlarm();
  const role = useRole();
  const canAck = role !== "observer";

  return (
    <div>
      <PageHeader
        title="Alarms & Events"
        subtitle="Safety alarms and significant events across the fleet"
        actions={
          <div className="flex items-center gap-1 rounded-md border border-[var(--color-hairline)] p-0.5">
            <Toggle on={activeOnly} onClick={() => setActiveOnly(true)}>
              Active
            </Toggle>
            <Toggle on={!activeOnly} onClick={() => setActiveOnly(false)}>
              All
            </Toggle>
          </div>
        }
      />

      <div className="p-6">
        <Panel>
          <PanelHeader eyebrow="Safety" title={`${(alarms.data ?? []).length} alarms`} />
          <div className="divide-y divide-[var(--color-hairline)]">
            {(alarms.data ?? []).length === 0 ? (
              <div className="px-4 py-12 text-center text-sm text-[var(--color-ink-faint)]">
                {activeOnly ? "No active alarms. All units within limits." : "No alarms recorded."}
              </div>
            ) : (
              (alarms.data ?? []).map((al) => (
                <div key={al.id} className="flex items-center gap-3 px-4 py-3 text-sm">
                  <Badge color={severityColor(al.severity)}>{al.severity}</Badge>
                  <span className="readout text-xs text-[var(--color-ink)]">{al.code}</span>
                  <span className="flex-1 truncate text-[var(--color-ink-dim)]">{al.message}</span>
                  <span className="readout text-[11px] text-[var(--color-ink-faint)]">
                    {fmtTime(al.ts_utc).slice(0, 19)}
                  </span>
                  {al.acknowledged ? (
                    <Badge color="var(--color-offline)">
                      <Check size={11} /> ack
                    </Badge>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!canAck || ack.isPending}
                      onClick={() => ack.mutate(al.id)}
                    >
                      Acknowledge
                    </Button>
                  )}
                </div>
              ))
            )}
          </div>
        </Panel>
        {!canAck ? (
          <p className="mt-3 text-xs text-[var(--color-ink-faint)]">
            Your role is read-only. Operators and above can acknowledge alarms.
          </p>
        ) : null}
      </div>
    </div>
  );
}

function Toggle({
  on,
  onClick,
  children,
}: {
  on: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className="rounded px-3 py-1 text-xs transition-colors"
      style={
        on
          ? { background: "var(--color-surface-3)", color: "var(--color-active)" }
          : { color: "var(--color-ink-faint)" }
      }
    >
      {children}
    </button>
  );
}
