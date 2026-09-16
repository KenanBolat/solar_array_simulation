"use client";

import { useMemo } from "react";
import { PageHeader } from "@/components/PageHeader";
import { RackVisual } from "@/components/RackVisual";
import { useDevices, useRacks } from "@/lib/hooks";
import type { Device } from "@/lib/types";

export default function RackExplorerPage() {
  const racks = useRacks();
  const devices = useDevices();

  const byRack = useMemo(() => {
    const map = new Map<string, Device[]>();
    for (const d of devices.data ?? []) {
      const arr = map.get(d.rack_id) ?? [];
      arr.push(d);
      map.set(d.rack_id, arr);
    }
    return map;
  }, [devices.data]);

  return (
    <div>
      <PageHeader
        title="Rack Explorer"
        subtitle="Physical hierarchy — rack, mainframe, module, channel"
      />
      <div className="grid grid-cols-1 gap-4 p-6 md:grid-cols-2 xl:grid-cols-3">
        {(racks.data ?? [])
          .slice()
          .sort((a, b) => a.position - b.position)
          .map((r) => (
            <RackVisual
              key={r.id}
              name={r.name}
              location={r.location}
              devices={(byRack.get(r.id) ?? [])
                .slice()
                .sort((a, b) => a.name.localeCompare(b.name))}
            />
          ))}
      </div>
    </div>
  );
}
