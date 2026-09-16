"use client";
import { useCallback, useEffect, useRef, useState } from "react";

export function usePoll<T>(fetcher: () => Promise<T>, intervalMs: number, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const reload = useCallback(() => {
    fetcherRef.current().then(setData).catch((e) => setError(e instanceof Error ? e : new Error(String(e))));
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;
    const tick = () => {
      fetcherRef.current()
        .then((d) => { if (!cancelled) setData(d); })
        .catch((e) => { if (!cancelled) setError(e instanceof Error ? e : new Error(String(e))); });
    };
    tick();
    if (intervalMs > 0) timer = setInterval(tick, intervalMs);
    return () => { cancelled = true; if (timer) clearInterval(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, reload };
}
