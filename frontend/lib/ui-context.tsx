"use client";
import { createContext, useCallback, useContext, useRef, useState } from "react";

export interface ConfirmConfig {
  title: string;
  message: string;
  confirmLabel: string;
  danger?: boolean;
  onConfirm: () => void;
}

interface UiCtx {
  notify: (msg: string) => void;
  ask: (cfg: ConfirmConfig) => void;
}

const Ctx = createContext<UiCtx | null>(null);

export function useUi() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useUi must be used within AppUiProvider");
  return ctx;
}

export function AppUiProvider({ children }: { children: React.ReactNode }) {
  const [toast, setToast] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<ConfirmConfig | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const notify = useCallback((msg: string) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setToast(msg);
    timerRef.current = setTimeout(() => setToast(null), 2600);
  }, []);

  const ask = useCallback((cfg: ConfirmConfig) => setConfirm(cfg), []);

  return (
    <Ctx.Provider value={{ notify, ask }}>
      {children}

      {confirm && (
        <div data-testid="confirm-modal" className="fixed inset-0 z-[70] flex items-center justify-center bg-[#05070ac4] animate-scfade">
          <div className="w-[440px] rounded-xl border border-line2 bg-panel p-[22px] shadow-[0_24px_70px_rgba(0,0,0,0.6)]">
            <div className="mb-3.5 flex gap-3">
              <div
                className="flex h-[34px] w-[34px] flex-none items-center justify-center rounded-md text-lg"
                style={{
                  background: confirm.danger ? "#f871711f" : "#fbbf241f",
                  color: confirm.danger ? "#f87171" : "#fbbf24",
                }}
              >
                ⚠
              </div>
              <div className="text-[15px] font-bold">{confirm.title}</div>
            </div>
            <div className="mb-5 text-[13px] leading-relaxed text-[#a9b2c0]">{confirm.message}</div>
            <div className="flex justify-end gap-2.5">
              <button
                onClick={() => setConfirm(null)}
                className="rounded-md border border-line2 bg-panel2 px-[18px] py-2 text-[13px] font-semibold text-ink"
              >
                Cancel
              </button>
              <button
                onClick={() => { const c = confirm; setConfirm(null); c.onConfirm(); }}
                className="rounded-md px-[18px] py-2 text-[13px] font-semibold"
                style={{
                  background: confirm.danger ? "#f87171" : "#34d399",
                  color: confirm.danger ? "#fff" : "#04130c",
                }}
              >
                {confirm.confirmLabel}
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div className="fixed bottom-[26px] left-1/2 z-[80] -translate-x-1/2 animate-scfade rounded-lg border border-line2 border-l-[3px] border-l-cyan bg-panel2 px-[18px] py-[11px] font-mono text-[12.5px] text-ink shadow-[0_10px_34px_rgba(0,0,0,0.5)]">
          {toast}
        </div>
      )}
    </Ctx.Provider>
  );
}
