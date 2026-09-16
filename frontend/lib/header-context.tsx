"use client";
import { createContext, useContext, useEffect, useState } from "react";

interface HeaderState {
  title: string;
  sub?: string;
}

interface HeaderCtx extends HeaderState {
  setHeader: (h: HeaderState) => void;
}

const Ctx = createContext<HeaderCtx | null>(null);

export function HeaderProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<HeaderState>({ title: "" });
  return <Ctx.Provider value={{ ...state, setHeader: setState }}>{children}</Ctx.Provider>;
}

export function useHeaderState() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useHeaderState must be used within HeaderProvider");
  return ctx;
}

/** Pages call this to set the top bar title/subtitle. */
export function usePageHeader(title: string, sub?: string) {
  const { setHeader } = useHeaderState();
  useEffect(() => {
    setHeader({ title, sub });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, sub]);
}
