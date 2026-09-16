"use client";

import { useRouter } from "next/navigation";
import type { Device } from "@/lib/types";
import { fmt, stateColor, stateLabel } from "@/lib/utils";

/**
 * The signature element: a rack rendered as a physical frame of 1U bays, each
 * lit by its device's live state. Cyan/green = healthy, amber = warning, red =
 * alarm, slate = offline. Bays are keyboard-focusable and open the control
 * page. This is the one place the UI leans into the instrument metaphor; the
 * rest of the app stays quiet around it.
 */
export function RackVisual({
  name,
  location,
  devices,
}: {
  name: string;
  location?: string;
  devices: Device[];
}) {
  const router = useRouter();

  return (
    <div className="panel overflow-hidden">
      <div className="panel-header">
        <div className="flex flex-col gap-0.5">
          <span className="eyebrow">Rack</span>
          <span className="text-sm font-semibold">{name}</span>
        </div>
        <span className="text-xs text-[var(--color-ink-faint)]">
          {devices.length} units{location ? ` · ${location}` : ""}
        </span>
      </div>

      {/* Rack frame: rails on either side, bays stacked between. */}
      <div className="flex gap-1.5 p-3">
        <RackRail />
        <div className="flex flex-1 flex-col gap-1">
          {devices.map((d) => {
            const st = d.last_state || {};
            const color = stateColor(st.device_state);
            const live = st.device_state && st.device_state !== "offline";
            return (
              <button
                key={d.id}
                onClick={() => router.push(`/devices/${d.id}`)}
                className="group grid grid-cols-[auto_1fr_auto] items-center gap-3 rounded-[5px] border border-[var(--color-hairline)] bg-[var(--color-base)] px-3 py-2 text-left transition-colors hover:border-[var(--color-hairline-strong)] hover:bg-[var(--color-surface-2)]"
              >
                <span
                  className={`status-dot ${st.device_state === "alarm" ? "status-pulse" : ""}`}
                  style={{ color, background: color }}
                />
                <div className="min-w-0">
                  <div className="truncate text-xs font-medium text-[var(--color-ink)]">
                    {d.name}
                  </div>
                  <div className="text-[10px] text-[var(--color-ink-faint)]">
                    {stateLabel(st.device_state)}
                    {st.output_enabled ? " · OUT" : ""}
                  </div>
                </div>
                <div className="readout text-right text-[11px] leading-tight text-[var(--color-ink-dim)]">
                  {live ? (
                    <>
                      <div>
                        <span className="text-[var(--color-ink)]">{fmt(st.voltage_v, 1)}</span>
                        <span className="text-[var(--color-ink-faint)]"> V</span>
                      </div>
                      <div>
                        <span className="text-[var(--color-ink)]">{fmt(st.power_w, 0)}</span>
                        <span className="text-[var(--color-ink-faint)]"> W</span>
                      </div>
                    </>
                  ) : (
                    <span className="text-[var(--color-ink-faint)]">— offline —</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
        <RackRail />
      </div>
    </div>
  );
}

function RackRail() {
  return (
    <div className="flex w-2 flex-col items-center justify-between rounded bg-[var(--color-surface-3)] py-2">
      {Array.from({ length: 8 }).map((_, i) => (
        <span key={i} className="h-1 w-1 rounded-full bg-[var(--color-hairline-strong)]" />
      ))}
    </div>
  );
}
