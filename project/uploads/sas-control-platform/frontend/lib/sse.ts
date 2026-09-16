"use client";

import { useEffect, useRef } from "react";
import { API_BASE } from "./api";

export type StreamChannel =
  | "measurements"
  | "device_state"
  | "command_status"
  | "alarms"
  | "scenario_progress";

/**
 * Subscribe to a live SSE channel. The handler receives the parsed JSON
 * payload. EventSource cannot send custom headers, but the backend's dev-auth
 * falls back to the view-capable observer user, so the stream connects without
 * one. If the stream drops, the surrounding TanStack Query polls keep the UI
 * current — SSE is a low-latency enhancement, not the only path.
 */
export function useStream(
  channel: StreamChannel,
  onMessage: (payload: Record<string, unknown>) => void,
  enabled = true
) {
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;
    const es = new EventSource(`${API_BASE}/api/stream/${channel}`);
    const listener = (e: MessageEvent) => {
      try {
        handlerRef.current(JSON.parse(e.data));
      } catch {
        /* ignore malformed frames */
      }
    };
    es.addEventListener(channel, listener as EventListener);
    es.onerror = () => {
      // let the browser auto-reconnect; polling covers the gap
    };
    return () => {
      es.removeEventListener(channel, listener as EventListener);
      es.close();
    };
  }, [channel, enabled]);
}
