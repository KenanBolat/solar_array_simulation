"use client";

/*
  Hardware readiness — pre-flight before connecting real instruments.

  Read-only. Answers one question: what would actually happen if an operator
  pressed a control right now. Three sections, in the order they gate each
  other:

    1. Gates       configuration switches that must be cleared, in order
    2. Templates   which operator-facing commands are live vs. blocked
    3. Operations  the SCPI verification table, with what to look up

  This screen exists because "is the platform ready for hardware" is otherwise
  spread across a config file, a driver table and an env var. Getting it wrong
  means either a command that silently does nothing, or one that reaches an
  energised supply unverified.
*/

import { AlertTriangle, Check, CircleDashed, X } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Panel, PanelHeader, Badge } from "@/components/ui/kit";
import { useHardwareReadiness } from "@/lib/hooks";

export default function HardwareReadinessPage() {
  const q = useHardwareReadiness();
  const d = q.data;

  const allGatesOpen = d ? d.summary.gates_open === d.summary.total_gates : false;

  return (
    <div>
      <PageHeader
        title="Hardware readiness"
        subtitle="Pre-flight checklist for connecting real instruments"
        actions={
          d ? (
            <Badge color={d.simulation_mode ? "var(--color-warning)" : "var(--color-alarm)"}>
              {d.simulation_mode ? "simulation mode" : "hardware enabled"}
            </Badge>
          ) : null
        }
      />

      <div className="space-y-4 p-6">
        {/* headline */}
        {d ? (
          <div
            className="flex items-start gap-3 rounded-[var(--radius-panel)] border p-4"
            style={{
              borderColor: allGatesOpen
                ? "color-mix(in srgb, var(--color-alarm) 40%, transparent)"
                : "color-mix(in srgb, var(--color-warning) 35%, transparent)",
              background: allGatesOpen
                ? "color-mix(in srgb, var(--color-alarm) 8%, transparent)"
                : "color-mix(in srgb, var(--color-warning) 7%, transparent)",
            }}
          >
            <AlertTriangle
              size={18}
              className="mt-0.5 shrink-0"
              style={{ color: allGatesOpen ? "var(--color-alarm)" : "var(--color-warning)" }}
            />
            <div className="space-y-1">
              <p className="text-sm font-semibold text-[var(--color-ink)]">
                {allGatesOpen
                  ? "Live hardware control is enabled"
                  : `${d.summary.total_gates - d.summary.gates_open} gate(s) still closed — commands are not reaching hardware`}
              </p>
              <p className="text-xs leading-relaxed text-[var(--color-ink-dim)]">
                {allGatesOpen
                  ? "Commands from every surface reach real instruments. Hardware interlocks and instrument-side OVP/OCP remain the only protection that acts without software in the loop."
                  : "Unverified operations are refused by the driver. This is the intended state until every SCPI string has been confirmed against the programming manual for your firmware revision."}
              </p>
            </div>
          </div>
        ) : null}

        {/* summary counters */}
        <div className="grid grid-cols-3 gap-px overflow-hidden rounded-[var(--radius-panel)] border border-[var(--color-hairline)] bg-[var(--color-hairline)]">
          <Counter
            label="Gates cleared"
            value={d ? `${d.summary.gates_open} / ${d.summary.total_gates}` : "—"}
            ok={d ? d.summary.gates_open === d.summary.total_gates : undefined}
          />
          <Counter
            label="Commands live"
            value={d ? `${d.summary.live_templates} / ${d.summary.total_templates}` : "—"}
            ok={d ? d.summary.live_templates === d.summary.total_templates : undefined}
          />
          <Counter
            label="SCPI verified"
            value={d ? `${d.summary.verified_ops} / ${d.summary.total_ops}` : "—"}
            ok={d ? d.summary.verified_ops === d.summary.total_ops : undefined}
          />
        </div>

        {/* gates */}
        <Panel>
          <PanelHeader
            eyebrow="Step 1"
            title="Configuration gates"
            actions={
              <span className="text-xs text-[var(--color-ink-faint)]">
                clear in order
              </span>
            }
          />
          <div className="divide-y divide-[var(--color-hairline)]">
            {(d?.gates ?? []).map((g, i) => (
              <div key={g.id} className="flex items-start gap-3 px-4 py-3">
                <span className="readout mt-0.5 w-4 shrink-0 text-xs text-[var(--color-ink-faint)]">
                  {i + 1}
                </span>
                <StateIcon ok={g.ok} />
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-[var(--color-ink)]">{g.label}</div>
                  <div className="readout text-xs text-[var(--color-ink-faint)]">{g.detail}</div>
                </div>
              </div>
            ))}
            {!d && q.isLoading ? <Loading /> : null}
          </div>
        </Panel>

        {/* templates */}
        <Panel>
          <PanelHeader
            eyebrow="Step 2"
            title="Operator commands"
            actions={
              <span className="text-xs text-[var(--color-ink-faint)]">
                what the UI can actually send
              </span>
            }
          />
          <div className="divide-y divide-[var(--color-hairline)]">
            {(d?.templates ?? []).map((t) => (
              <div key={t.id} className="flex items-center gap-3 px-4 py-2.5">
                <StateIcon ok={t.live} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-[var(--color-ink)]">{t.title}</span>
                    {t.hazardous ? (
                      <Badge color="var(--color-warning)">hazardous</Badge>
                    ) : null}
                  </div>
                  <div className="readout text-xs text-[var(--color-ink-faint)]">
                    {t.id}
                    {t.blocked_by.length > 0 ? ` · blocked by ${t.blocked_by.join(", ")}` : ""}
                  </div>
                </div>
                <span
                  className="readout shrink-0 text-xs font-semibold"
                  style={{ color: t.live ? "var(--color-output)" : "var(--color-ink-faint)" }}
                >
                  {t.live ? "LIVE" : "BLOCKED"}
                </span>
              </div>
            ))}
            {!d && q.isLoading ? <Loading /> : null}
          </div>
        </Panel>

        {/* operations */}
        <Panel>
          <PanelHeader
            eyebrow="Step 3"
            title="SCPI verification table"
            actions={
              <span className="text-xs text-[var(--color-ink-faint)]">
                app/drivers/e4360.py
              </span>
            }
          />
          <div className="divide-y divide-[var(--color-hairline)]">
            {(d?.operations ?? []).map((o) => (
              <div key={o.op} className="px-4 py-2.5">
                <div className="flex items-center gap-3">
                  <StateIcon ok={o.verified} />
                  <span className="readout min-w-0 flex-1 text-sm text-[var(--color-ink)]">
                    {o.op}
                  </span>
                  <div className="flex shrink-0 gap-1">
                    <Kind on={o.has_query} label="query" />
                    <Kind on={o.has_write} label="write" />
                    <Kind on={o.has_readback} label="readback" />
                  </div>
                </div>
                {!o.verified && o.note ? (
                  <p className="mt-1.5 pl-[30px] text-xs leading-relaxed text-[var(--color-ink-faint)]">
                    {o.note}
                  </p>
                ) : null}
              </div>
            ))}
            {!d && q.isLoading ? <Loading /> : null}
          </div>
          <div className="border-t border-[var(--color-hairline)] px-4 py-3">
            <p className="text-xs leading-relaxed text-[var(--color-ink-faint)]">
              Every write should have a paired readback query — the platform verifies
              setpoints after each state change, and reports an unverified readback as a
              warning rather than a success. Full procedure in{" "}
              <span className="readout text-[var(--color-ink-dim)]">
                docs/BRINGUP_RUNBOOK.md
              </span>
              .
            </p>
          </div>
        </Panel>

        {q.isError ? (
          <p className="text-sm text-[var(--color-alarm)]">
            Could not load readiness state: {(q.error as Error).message}
          </p>
        ) : null}
      </div>
    </div>
  );
}

function StateIcon({ ok }: { ok: boolean }) {
  return ok ? (
    <Check size={15} className="mt-0.5 shrink-0" style={{ color: "var(--color-output)" }} />
  ) : (
    <X size={15} className="mt-0.5 shrink-0" style={{ color: "var(--color-ink-faint)" }} />
  );
}

function Kind({ on, label }: { on: boolean; label: string }) {
  return (
    <span
      className="rounded border px-1.5 py-0.5 text-[10px] font-medium"
      style={{
        borderColor: on ? "color-mix(in srgb, var(--color-active) 35%, transparent)" : "var(--color-hairline)",
        color: on ? "var(--color-active)" : "var(--color-ink-faint)",
        background: on ? "color-mix(in srgb, var(--color-active) 10%, transparent)" : "transparent",
      }}
    >
      {label}
    </span>
  );
}

function Counter({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="bg-[var(--color-surface)] px-4 py-3">
      <div className="eyebrow">{label}</div>
      <div
        className="readout mt-1 text-2xl font-semibold"
        style={{
          color:
            ok === undefined
              ? "var(--color-ink)"
              : ok
                ? "var(--color-output)"
                : "var(--color-warning)",
        }}
      >
        {value}
      </div>
    </div>
  );
}

function Loading() {
  return (
    <div className="flex items-center gap-2 px-4 py-6 text-sm text-[var(--color-ink-faint)]">
      <CircleDashed size={14} className="animate-spin" /> Reading driver state…
    </div>
  );
}
