import { create } from "zustand";
import type { Role } from "./types";

// UI-only state (Zustand is intentionally NOT used for server data — that
// lives in TanStack Query). In development the selected role is sent as the
// X-Dev-User header so you can exercise RBAC without a login screen.
interface UiState {
  role: Role;
  setRole: (r: Role) => void;
  chartsPaused: boolean;
  toggleChartsPaused: () => void;
}

const initialRole: Role =
  (typeof window !== "undefined" && (localStorage.getItem("sas_role") as Role)) || "operator";

export const useUiStore = create<UiState>((set) => ({
  role: initialRole,
  setRole: (role) => {
    if (typeof window !== "undefined") localStorage.setItem("sas_role", role);
    set({ role });
  },
  chartsPaused: false,
  toggleChartsPaused: () => set((s) => ({ chartsPaused: !s.chartsPaused })),
}));
