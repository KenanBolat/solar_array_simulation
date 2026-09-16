"use client";

import { useMemo, useState } from "react";
import { PageHeader } from "@/components/PageHeader";
import { Panel, PanelHeader, Select } from "@/components/ui/kit";
import { useAuditLog } from "@/lib/hooks";
import { fmtTime } from "@/lib/utils";

const OUTCOME_COLOR: Record<string, string> = {
  completed: "var(--color-output)",
  rejected: "var(--color-alarm)",
  failed: "var(--color-alarm)",
  timed_out: "var(--color-alarm)",
  blocked: "var(--color-warning)",
};

export default function CommandHistoryPage() {
  const audit = useAuditLog(500);
  const [outcome, setOutcome] = useState("all");
  const [actor, setActor] = useState("all");

  const actors = useMemo(
    () => Array.from(new Set((audit.data ?? []).map((a) => a.actor))).sort(),
    [audit.data]
  );

  const rows = (audit.data ?? []).filter(
    (a) =>
      (outcome === "all" || a.outcome === outcome) && (actor === "all" || a.actor === actor)
  );

  return (
    <div>
      <PageHeader
        title="Command History"
        subtitle="Append-only audit trail of every issued command"
        actions={
          <div className="flex items-center gap-2">
            <Select value={actor} onChange={(e) => setActor(e.target.value)}>
              <option value="all">All actors</option>
              {actors.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </Select>
            <Select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
              <option value="all">All outcomes</option>
              <option value="completed">Completed</option>
              <option value="rejected">Rejected</option>
              <option value="blocked">Blocked</option>
              <option value="failed">Failed</option>
            </Select>
          </div>
        }
      />

      <div className="p-6">
        <Panel>
          <PanelHeader eyebrow="Audit" title={`${rows.length} entries`} />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--color-hairline)] text-left text-xs text-[var(--color-ink-faint)]">
                  <th className="px-4 py-2 font-medium">Timestamp (UTC)</th>
                  <th className="px-4 py-2 font-medium">Actor</th>
                  <th className="px-4 py-2 font-medium">Action</th>
                  <th className="px-4 py-2 font-medium">Outcome</th>
                  <th className="px-4 py-2 font-medium">Correlation</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((a) => (
                  <tr key={a.id} className="border-b border-[var(--color-hairline)]/60">
                    <td className="readout px-4 py-2 text-xs text-[var(--color-ink-dim)]">
                      {fmtTime(a.ts_utc).slice(0, 19)}
                    </td>
                    <td className="px-4 py-2 text-[var(--color-ink-dim)]">{a.actor}</td>
                    <td className="readout px-4 py-2 text-xs text-[var(--color-ink)]">
                      {a.action}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className="inline-flex items-center gap-1.5 text-xs"
                        style={{ color: OUTCOME_COLOR[a.outcome] ?? "var(--color-ink-dim)" }}
                      >
                        <span
                          className="status-dot"
                          style={{
                            color: OUTCOME_COLOR[a.outcome] ?? "var(--color-ink-faint)",
                            background: OUTCOME_COLOR[a.outcome] ?? "var(--color-ink-faint)",
                          }}
                        />
                        {a.outcome}
                      </span>
                    </td>
                    <td className="readout px-4 py-2 text-[11px] text-[var(--color-ink-faint)]">
                      {a.correlation_id.slice(0, 8)}
                    </td>
                  </tr>
                ))}
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-sm text-[var(--color-ink-faint)]">
                      No matching audit entries.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </div>
  );
}
