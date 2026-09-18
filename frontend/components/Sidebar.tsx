"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";

export function Sidebar() {
  const pathname = usePathname();
  const { data: units } = usePoll(() => api.units(), 15000);
  const firstUnit = units?.find((u) => u.enabled)?.name ?? units?.[0]?.name ?? null;
  const controlHref = firstUnit ? `/control/${firstUnit}` : "/overview";

  const navItems: { label: string; href: string }[] = [
    { label: "Overview", href: "/overview" },
    { label: "Simulator Control", href: controlHref },
    { label: "Measurements", href: "/measurements" },
    { label: "Scenario Builder", href: "/scenarios/builder" },
    { label: "Scenario Runs", href: "/scenarios/runs" },
    { label: "Command History", href: "/command-history" },
    { label: "Alarms", href: "/alarms" },
    { label: "Configuration", href: "/config" },
  ];

  return (
    <aside className="flex h-screen w-[218px] flex-none flex-col border-r border-line bg-[#0e1117]">
      <div className="border-b border-line px-4 pb-3.5 pt-[18px]">
        <div className="flex items-center gap-2.5">
          <div className="flex h-[26px] w-[26px] items-center justify-center rounded-md border border-cyan/40 bg-cyan/10">
            <div className="h-[11px] w-[11px] rounded-sm border-2 border-cyan" />
          </div>
          <div>
            <div className="text-[12px] font-bold leading-tight tracking-wide">SAS Control</div>
            <div className="font-mono text-[9.5px] tracking-wider text-faint">PLATFORM v0.1</div>
          </div>
        </div>
      </div>
      <nav className="flex-1 overflow-auto py-2">
        {navItems.map((item, idx) => {
          const active = item.label === "Simulator Control" ? pathname.startsWith("/control") : pathname === item.href;
          return (
            <Link
              key={item.label + idx}
              href={item.href}
              className="mx-2 my-px flex items-center gap-2.5 rounded-md px-3.5 py-2.5 text-[13px]"
              style={{
                fontWeight: active ? 600 : 500,
                color: active ? "#fff" : "#8a95a8",
                background: active ? "#2dd4ee18" : "transparent",
                borderLeft: `2px solid ${active ? "#2dd4ee" : "transparent"}`,
              }}
            >
              <span
                className="h-[5px] w-[5px] flex-none rounded-full"
                style={{ background: active ? "#2dd4ee" : "#5c6678" }}
              />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="flex items-center gap-2.5 border-t border-line px-4 py-3">
        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-line2 text-[11px] font-semibold text-ink">
          AN
        </div>
        <div className="leading-tight">
          <div className="text-[12px] font-semibold">a.ng</div>
          <div className="text-[10px] text-faint">Operator · L2</div>
        </div>
      </div>
    </aside>
  );
}
