"use client";

import { useEffect, useState } from "react";
import { Ban, Pause, Play } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Panel, PanelHeader, Badge, Button } from "@/components/ui/kit";
import { useRunControl, useRunEvents, useScenarioRuns } from "@/lib/hooks";
import { fmtTime, relTime } from "@/lib/utils";

const STATUS_COLOR: Record<string, string> = {
  completed: "var(--color-output)",
  running: "var(--color-active)",
  paused: "var(--color-warning)",
  aborted: "var(--color-offline)",
  failed: "var(--color-alarm)",
  pending: "var(--color-ink-faint)",
};

export default function ScenarioRunsPage() {
  const runs = useScenarioRuns();
  const [selected, setSelected] = useState<string | null>(null);
  const events = useRunEvents(selected ?? "");
  const control = useRunControl();

  useEffect(() => {
    if (!selected && runs.data && runs.data.length > 0) setSelected(runs.data[0].id);
  }, [runs.data, selected]);

  const active = runs.data?.find((r) => r.id === selected);

  return (
    <div>
      <PageHeader title="Scenario Runs" subtitle="Execution history and live progress" />
      <div className="grid grid-cols-1 gap-4 p-6 lg:grid-cols-[1fr_1.2fr]">
        <Panel>
          <PanelHeader eyebrow="History" title="Runs" />
          <div className="divide-y divide-[var(--color-hairline)]">
            {(runs.data ?? []).length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-[var(--color-ink-faint)]">
                No runs yet. Start one from the Scenario Builder.
              </div>
            ) : (
              (runs.data ?? []).map((r) => (
                <button
                  key={r.id}
                  onClick={() => setSelected(r.id)}
                  className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm transition-colors hover:bg-[var(--color-surface-2)]"
                  style={r.id === selected ? { background: "var(--color-surface-2)" } : undefined}
                >
                  <Badge color={STATUS_COLOR[r.status] ?? "var(--color-ink-faint)"}>{r.status}</Badge>
                  {r.dry_run ? <Badge color="var(--color-offline)">dry</Badge> : null}
                  <div className="ml-1 flex-1">
                    <div className="readout text-xs text-[var(--color-ink)]">
                      v{r.version} · {Math.round(r.progress * 100)}%
                    </div>
                    <div className="text-[11px] text-[var(--color-ink-faint)]">
                      {r.started_utc ? relTime(r.started_utc) : "—"}
                    </div>
                  </div>
                  <ProgressBar value={r.progress} color={STATUS_COLOR[r.status]} />
                </button>
              ))
            )}
          </div>
        </Panel>

        <Panel>
          <PanelHeader
            eyebrow="Live log"
            title={active ? `Run ${active.id.slice(0, 8)}` : "Event log"}
            actions={
              active ? (
                <div className="flex items-center gap-1">
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={active.status !== "running" || control.isPending}
                    onClick={() => control.mutate({ runId: active.id, action: "pause" })}
                  >
                    <Pause size={13} /> Pause
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={active.status !== "paused" || control.isPending}
                    onClick={() => control.mutate({ runId: active.id, action: "resume" })}
                  >
                    <Play size={13} /> Resume
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={!["running", "paused"].includes(active.status) || control.isPending}
                    onClick={() => control.mutate({ runId: active.id, action: "abort" })}
                  >
                    <Ban size={13} /> Abort
                  </Button>
                </div>
              ) : null
            }
          />
          <div className="max-h-[60vh] space-y-0.5 overflow-y-auto p-3">
            {(events.data ?? []).length === 0 ? (
              <div className="px-2 py-8 text-center text-sm text-[var(--color-ink-faint)]">
                No events for this run.
              </div>
            ) : (
              (events.data ?? []).map((e, i) => (
                <div
                  key={i}
                  className="readout flex items-start gap-2 rounded px-2 py-1 text-xs"
                  style={{
                    color:
                      e.level === "error"
                        ? "var(--color-alarm)"
                        : e.level === "warn"
                          ? "var(--color-warning)"
                          : "var(--color-ink-dim)",
                  }}
                >
                  <span className="shrink-0 text-[var(--color-ink-faint)]">
                    {fmtTime(e.ts_utc).slice(11, 19)}
                  </span>
                  {e.node_key ? (
                    <span className="shrink-0 text-[var(--color-ink-faint)]">[{e.node_key}]</span>
                  ) : null}
                  <span>{e.message}</span>
                </div>
              ))
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function ProgressBar({ value, color }: { value: number; color?: string }) {
  return (
    <div className="h-1.5 w-16 overflow-hidden rounded-full bg-[var(--color-hairline)]">
      <div
        className="h-full rounded-full"
        style={{ width: `${Math.round(value * 100)}%`, background: color ?? "var(--color-active)" }}
      />
    </div>
  );
}
