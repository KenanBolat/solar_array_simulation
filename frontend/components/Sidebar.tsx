"use client";
import Image from "next/image";
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
      <Link href="/" title="Back to the landing page"
        className="block border-b border-line px-4 pb-3.5 pt-[18px] hover:bg-[#ffffff06]">
        <div className="flex items-center gap-2.5">
          {/* The compact mark, not the full illustration: below ~40 px the orbit
              ring, rays and antenna alias away and the whole scene reads as a
              smudge. Fixed box so the row height never shifts while it loads. */}
          <Image src="/logo-mark.webp" alt="" width={36} height={36} priority
            className="h-9 w-9 flex-none" />
          <div>
            <div className="text-[12px] font-bold leading-tight tracking-wide">SAS Control</div>
            <div className="font-mono text-[9.5px] tracking-wider text-faint">PLATFORM v0.1</div>
          </div>
        </div>
      </Link>
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
    </aside>
  );
}
