"use client";
import { createContext, useContext, useMemo, useState } from "react";

/** Shared state for every chart inside one ChartSyncProvider: the time the
 *  pointer is on, and the zoom window. Both are in epoch milliseconds, so
 *  charts with different sampling rates still line up on the same instant. */
export interface ChartSyncValue {
  hoverTs: number | null;
  setHoverTs: (t: number | null) => void;
  domain: [number, number] | null;   // null = full extent
  setDomain: (d: [number, number] | null) => void;
}

const Ctx = createContext<ChartSyncValue | null>(null);

export function ChartSyncProvider({ children }: { children: React.ReactNode }) {
  const [hoverTs, setHoverTs] = useState<number | null>(null);
  const [domain, setDomain] = useState<[number, number] | null>(null);
  const value = useMemo(() => ({ hoverTs, setHoverTs, domain, setDomain }), [hoverTs, domain]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** Charts outside a provider (or in fullscreen) keep their own local state. */
export function useChartSync(enabled = true): ChartSyncValue {
  const shared = useContext(Ctx);
  const [hoverTs, setHoverTs] = useState<number | null>(null);
  const [domain, setDomain] = useState<[number, number] | null>(null);
  const local = useMemo(() => ({ hoverTs, setHoverTs, domain, setDomain }), [hoverTs, domain]);
  return enabled && shared ? shared : local;
}
