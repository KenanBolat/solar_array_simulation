"use client";

import { TriangleAlert } from "lucide-react";
import { useMeta } from "@/lib/hooks";

/**
 * Persistent banner. Whenever the platform is not bound to real hardware it
 * states SIMULATION MODE unmistakably, per the safety requirements. If
 * hardware is ever enabled it switches to a live-hardware caution instead.
 */
export function SimulationBanner() {
  const { data } = useMeta();
  const sim = data ? data.simulation_mode : true; // assume simulation until told otherwise

  if (sim) {
    return (
      <div
        className="flex items-center justify-center gap-2 px-4 py-1.5 text-xs font-semibold tracking-wide"
        style={{
          color: "var(--color-active)",
          background: "color-mix(in srgb, var(--color-active) 10%, transparent)",
          borderBottom: "1px solid color-mix(in srgb, var(--color-active) 30%, transparent)",
        }}
      >
        <span className="status-dot status-pulse" style={{ color: "var(--color-active)", background: "var(--color-active)" }} />
        SIMULATION MODE — no physical instruments are connected. All readings and
        commands are synthetic.
      </div>
    );
  }
  return (
    <div
      className="flex items-center justify-center gap-2 px-4 py-1.5 text-xs font-bold tracking-wide"
      style={{
        color: "var(--color-alarm)",
        background: "color-mix(in srgb, var(--color-alarm) 14%, transparent)",
        borderBottom: "1px solid color-mix(in srgb, var(--color-alarm) 40%, transparent)",
      }}
    >
      <TriangleAlert size={14} />
      LIVE HARDWARE ENABLED — commands drive real instruments. Hardware limits are
      the ultimate authority.
    </div>
  );
}
