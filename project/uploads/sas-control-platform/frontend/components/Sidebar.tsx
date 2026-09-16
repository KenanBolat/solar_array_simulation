"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Server,
  SlidersHorizontal,
  Activity,
  Workflow,
  PlayCircle,
  History,
  BellRing,
  Settings,
  ShieldCheck,
  Sun,
  PlugZap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/lib/store";
import type { Role } from "@/lib/types";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/racks", label: "Rack Explorer", icon: Server },
  { href: "/devices", label: "Simulator Control", icon: SlidersHorizontal },
  { href: "/measurements", label: "Measurements", icon: Activity },
  { href: "/scenarios/builder", label: "Scenario Builder", icon: Workflow },
  { href: "/scenario-runs", label: "Scenario Runs", icon: PlayCircle },
  { href: "/command-history", label: "Command History", icon: History },
  { href: "/alarms", label: "Alarms & Events", icon: BellRing },
  { href: "/config", label: "Device Configuration", icon: Settings },
  { href: "/admin/hardware", label: "Hardware Readiness", icon: PlugZap },
  { href: "/admin", label: "Administration", icon: ShieldCheck },
];

const ROLES: Role[] = ["observer", "operator", "supervisor", "administrator"];

export function Sidebar() {
  const pathname = usePathname();
  const { role, setRole } = useUiStore();

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-[var(--color-hairline)] bg-[var(--color-surface)]">
      <div className="flex items-center gap-2.5 px-4 py-4">
        <div
          className="flex h-8 w-8 items-center justify-center rounded-md"
          style={{ background: "color-mix(in srgb, var(--color-active) 16%, transparent)" }}
        >
          <Sun size={18} style={{ color: "var(--color-active)" }} />
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold text-[var(--color-ink)]">SAS Control</span>
          <span className="text-[10px] tracking-wide text-[var(--color-ink-faint)]">
            GROUND SEGMENT
          </span>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 px-2 py-2">
        {NAV.map((item) => {
          const active =
            item.href === "/"
              ? pathname === "/"
              : item.href === "/admin"
                ? pathname === "/admin"
                : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-[var(--color-surface-3)] text-[var(--color-ink)]"
                  : "text-[var(--color-ink-dim)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-ink)]"
              )}
            >
              <Icon
                size={16}
                style={active ? { color: "var(--color-active)" } : undefined}
              />
              {item.label}
              {active ? (
                <span
                  className="ml-auto h-4 w-0.5 rounded-full"
                  style={{ background: "var(--color-active)" }}
                />
              ) : null}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-[var(--color-hairline)] p-3">
        <div className="eyebrow mb-1.5">Acting role (dev)</div>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as Role)}
          className="h-8 w-full rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] px-2 text-xs text-[var(--color-ink)] focus-visible:border-[var(--color-active)]"
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <p className="mt-1.5 text-[10px] leading-snug text-[var(--color-ink-faint)]">
          Sent as X-Dev-User. Replaced by SSO/JWT in production.
        </p>
      </div>
    </aside>
  );
}
