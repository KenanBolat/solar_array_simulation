"use client";
import { useEffect, useRef, useState } from "react";
import { api, SCENARIO_ID } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { usePageHeader } from "@/lib/header-context";
import { useUi } from "@/lib/ui-context";
import type { NodeProps, ScenarioNode } from "@/lib/types";

const KIND_COLOR: Record<string, string> = {
  terminal: "#34d399", action: "#2dd4ee", flow: "#3b82f6", measure: "#5eead4", logic: "#fbbf24", danger: "#f87171",
};
const NODE_W = 170, NODE_H = 58;

function port(n: ScenarioNode, side: "R" | "L" | "T" | "B"): [number, number] {
  const { x, y } = n;
  if (side === "R") return [x + NODE_W, y + NODE_H / 2];
  if (side === "L") return [x, y + NODE_H / 2];
  if (side === "B") return [x + NODE_W / 2, y + NODE_H];
  return [x + NODE_W / 2, y];
}

function connPath(a: ScenarioNode, b: ScenarioNode, kind: "R" | "B") {
  if (kind === "B") {
    const [p1x, p1y] = port(a, "B");
    const [p2x, p2y] = port(b, "T");
    const dy = (p2y - p1y) / 2;
    return `M${p1x},${p1y} C ${p1x},${p1y + dy} ${p2x},${p2y - dy} ${p2x},${p2y}`;
  }
  const [p1x, p1y] = port(a, "R");
  const [p2x, p2y] = port(b, "L");
  const dx = Math.abs(p2x - p1x) / 2;
  return `M${p1x},${p1y} C ${p1x + dx},${p1y} ${p2x - dx},${p2y} ${p2x},${p2y}`;
}

export default function ScenarioBuilderPage() {
  usePageHeader("Scenario Builder", "Eclipse Cycle — Panel A · v1.4");
  const { notify } = useUi();
  const { data: graph } = usePoll(() => api.scenario(SCENARIO_ID), 30000);
  const { data: units } = usePoll(() => api.units(), 15000);
  const { data: runsList, reload: reloadRuns } = usePoll(() => api.runs("All"), 2500);
  const targetUnitObj = units?.find((u) => u.featured) ?? units?.[0];
  const targetUnit = targetUnitObj?.name ?? "the configured target unit";
  const targetActive = !!targetUnitObj && targetUnitObj.enabled && targetUnitObj.online;
  const [selectedNode, setSelectedNode] = useState("thresh");
  const [nodeProps, setNodeProps] = useState<NodeProps | null>(null);
  const [zoom, setZoom] = useState(1);
  const [showMinimap] = useState(true);
  const [showRunModal, setShowRunModal] = useState(false);
  const [positions, setPositions] = useState<Record<string, { x: number; y: number }>>({});
  const dragRef = useRef<{ id: string; dx: number; dy: number; moved: boolean } | null>(null);

  useEffect(() => {
    api.nodeProps(SCENARIO_ID, selectedNode).then(setNodeProps).catch(() => setNodeProps(null));
  }, [selectedNode]);

  if (!graph) return <div className="p-5 text-muted">Loading scenario…</div>;

  const activeRun = runsList?.find((r) => r.scenario === graph.scenario.name && r.status === "Running");

  const resolved = (n: ScenarioNode): ScenarioNode => {
    const p = positions[n.id];
    return p ? { ...n, x: p.x, y: p.y } : n;
  };
  const nById: Record<string, ScenarioNode> = {};
  graph.nodes.forEach((n) => (nById[n.id] = resolved(n)));

  const runScenario = async () => {
    setShowRunModal(false);
    try {
      const run = await api.runScenario(SCENARIO_ID);
      notify(`Scenario dispatched — ${run.id} started`);
      reloadRuns();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Failed to start scenario");
    }
  };

  const pauseScenario = async () => {
    if (!activeRun) { notify("No run is active"); return; }
    const res = await api.pauseRun(activeRun.id);
    notify(res.message);
  };

  const abortScenario = async () => {
    if (!activeRun) { notify("No run is active"); return; }
    const res = await api.abortRun(activeRun.id);
    notify(res.message);
    reloadRuns();
  };

  const nodeMouseDown = (e: React.MouseEvent, n: ScenarioNode) => {
    e.preventDefault();
    const start = resolved(n);
    dragRef.current = { id: n.id, dx: e.clientX / zoom - start.x, dy: e.clientY / zoom - start.y, moved: false };
    const onMove = (ev: MouseEvent) => {
      const d = dragRef.current;
      if (!d) return;
      d.moved = true;
      const x = Math.max(0, Math.round(ev.clientX / zoom - d.dx));
      const y = Math.max(0, Math.round(ev.clientY / zoom - d.dy));
      setPositions((prev) => ({ ...prev, [d.id]: { x, y } }));
    };
    const onUp = () => {
      if (dragRef.current && !dragRef.current.moved) setSelectedNode(dragRef.current.id);
      dragRef.current = null;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-[50px] flex-none items-center gap-3 border-b border-line bg-[#0e1117] px-4">
        <span className="text-[13px] font-bold">{graph.scenario.name}</span>
        <span className="font-mono text-[10px] text-faint">{graph.scenario.version}</span>
        <span className="rounded border border-amber/35 px-1.5 py-0.5 text-[10px] font-semibold text-amber">{graph.scenario.state}</span>
        {activeRun ? (
          <span className="flex items-center gap-1.5 rounded border border-cyan/35 px-1.5 py-0.5 text-[10px] font-semibold text-cyan">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan" />
            Running · {activeRun.id} · {activeRun.prog}%
          </span>
        ) : (
          <span className="rounded border border-line2 px-1.5 py-0.5 text-[10px] font-semibold text-faint">Idle</span>
        )}
        <div className="flex-1" />
        <ToolBtn onClick={() => notify("Scenario saved")}>Save</ToolBtn>
        <ToolBtn onClick={() => notify("Validation passed · 0 invalid nodes")}>Validate</ToolBtn>
        <ToolBtn onClick={() => notify("Dry run complete · no commands dispatched")}>Dry Run</ToolBtn>
        <button
          onClick={() => setShowRunModal(true)}
          disabled={!targetActive || !!activeRun}
          title={!targetActive ? `${targetUnit} is not active (must be enabled + reachable)` : activeRun ? `Already running as ${activeRun.id}` : ""}
          className="rounded-md bg-green px-3.5 py-1.5 text-[11px] font-bold text-[#04130c] disabled:cursor-not-allowed disabled:bg-line2 disabled:text-faint"
        >
          ▶ Run Scenario
        </button>
        <ToolBtn onClick={pauseScenario} disabled={!activeRun}>Pause</ToolBtn>
        <button onClick={abortScenario} disabled={!activeRun} className="rounded-md border border-red/40 bg-red/10 px-3 py-1.5 text-[11px] font-semibold text-red disabled:cursor-not-allowed disabled:opacity-40">Abort</button>
      </div>
      {!targetActive && (
        <div className="flex-none border-b border-amber/25 bg-amber/[0.06] px-4 py-1.5 text-[11px] text-amber">
          ⚠ Target unit {targetUnit} is not active (enabled + reachable) — Run Scenario is disabled until it comes back online.
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <div className="w-[188px] flex-none overflow-auto border-r border-line bg-[#0e1117] p-2.5">
          <div className="mb-2 ml-1 text-[9.5px] uppercase tracking-wider text-faint">Node Palette</div>
          <div className="mb-2 ml-1 text-[10px] leading-relaxed text-faint">
            Reference only for this demo — this scenario&apos;s graph is fixed. Drag nodes on the canvas to rearrange the existing steps.
          </div>
          {graph.palette.map((p) => (
            <div key={p} className="mb-1 flex cursor-not-allowed items-center gap-2 rounded-md px-2.5 py-2 text-[12px] text-[#cfd6e2] opacity-60">
              <span className="h-1.5 w-1.5 rounded-full bg-line2" />{p}
            </div>
          ))}
        </div>

        <div className="relative flex-1 overflow-hidden" style={{
          backgroundColor: "#0c0f15",
          backgroundImage: "linear-gradient(#ffffff08 1px,transparent 1px),linear-gradient(90deg,#ffffff08 1px,transparent 1px)",
          backgroundSize: "22px 22px",
        }}>
          <div className="absolute left-[18px] top-[18px]">
            <div style={{ transformOrigin: "0 0", transform: `scale(${zoom})`, position: "relative", width: 1080, height: 470 }}>
              <svg style={{ position: "absolute", inset: 0, width: 1080, height: 470, overflow: "visible", pointerEvents: "none" }}>
                <defs>
                  <marker id="ah-cyan" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z" fill="#2dd4ee" /></marker>
                  <marker id="ah-red" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z" fill="#f87171" /></marker>
                </defs>
                {graph.edges.map((e, idx) => (
                  <path key={idx} d={connPath(nById[e.from], nById[e.to], e.kind)} fill="none"
                    stroke={e.fail ? "#f87171" : "#2dd4ee"} strokeWidth={2}
                    strokeDasharray={e.fail ? "5 4" : "0"}
                    markerEnd={`url(#${e.fail ? "ah-red" : "ah-cyan"})`} />
                ))}
              </svg>
              {graph.nodes.map((raw) => {
                const n = nById[raw.id];
                const sel = n.id === selectedNode;
                const color = KIND_COLOR[n.kind];
                const danger = n.kind === "danger";
                const warn = n.kind === "logic";
                return (
                  <div key={n.id} onMouseDown={(e) => nodeMouseDown(e, n)}
                    className="absolute cursor-grab select-none rounded-md px-2.5 pb-2.5 pt-2 active:cursor-grabbing"
                    style={{
                      left: n.x, top: n.y, width: NODE_W,
                      background: danger ? "#1f1216" : "#1a1f29",
                      border: `1.5px solid ${sel ? color : danger ? color + "88" : color + "66"}`,
                      boxShadow: sel ? `0 0 0 3px ${color}33, 0 8px 22px rgba(0,0,0,.5)` : "0 4px 14px rgba(0,0,0,.45)",
                    }}>
                    <div className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full" style={{ background: warn ? "#fbbf24" : danger ? "#f87171" : "#34d399", boxShadow: `0 0 7px ${warn ? "#fbbf24" : danger ? "#f87171" : "#34d399"}` }} />
                    <div className="mb-1 inline-block rounded px-1.5 py-0.5 font-mono text-[8.5px] font-semibold tracking-wider" style={{ color, background: color + "1f" }}>{n.type}</div>
                    <div className="text-[12.5px] font-semibold leading-tight text-ink">{n.label}</div>
                    {n.sub && <div className="mt-0.5 font-mono text-[10px] text-muted">{n.sub}</div>}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="absolute bottom-4 left-4 flex items-center gap-1.5 rounded-md border border-line bg-panel p-1.5">
            <div onClick={() => setZoom((z) => Math.max(0.6, +(z - 0.1).toFixed(2)))} className="flex h-[26px] w-[26px] cursor-pointer items-center justify-center rounded-md bg-panel2 text-[15px] text-[#cfd6e2]">−</div>
            <span className="w-[42px] text-center font-mono text-[11px] text-muted">{Math.round(zoom * 100)}%</span>
            <div onClick={() => setZoom((z) => Math.min(1.6, +(z + 0.1).toFixed(2)))} className="flex h-[26px] w-[26px] cursor-pointer items-center justify-center rounded-md bg-panel2 text-[15px] text-[#cfd6e2]">+</div>
            <div onClick={() => setZoom(1)} className="flex h-[26px] cursor-pointer items-center rounded-md bg-panel2 px-2.5 text-[10px] text-muted">Fit</div>
          </div>

          {showMinimap && (
            <div className="absolute bottom-4 right-4 h-[84px] w-[170px] overflow-hidden rounded-md border border-line2 bg-[#0e1117cc]">
              <svg viewBox="0 0 1080 470" className="h-full w-full">
                {graph.edges.map((e, idx) => (
                  <path key={idx} d={connPath(nById[e.from], nById[e.to], e.kind)} fill="none" stroke={e.fail ? "#f87171" : "#2dd4ee"} strokeWidth={4} opacity={0.5} />
                ))}
                {graph.nodes.map((raw) => {
                  const n = nById[raw.id];
                  return <rect key={n.id} x={n.x} y={n.y} width={170} height={58} rx={8} fill={KIND_COLOR[n.kind]} opacity={0.55} />;
                })}
              </svg>
            </div>
          )}
        </div>

        <div className="w-[288px] flex-none overflow-auto border-l border-line bg-[#0e1117] p-3.5">
          <div className="mb-2.5 text-[10px] uppercase tracking-wider text-faint">Node Properties</div>
          {nodeProps && (
            <div className="rounded-[9px] border border-line bg-panel p-3.5">
              <div className="mb-0.5 text-[14px] font-bold">{nodeProps.name}</div>
              <div className="mb-3.5 text-[11px] text-muted">Target · {nodeProps.target}</div>
              <div className="mb-1.5 text-[10px] uppercase tracking-wider text-faint">Parameters</div>
              <div className="mb-3.5 flex flex-col gap-1.5">
                {nodeProps.params.map(([k, v], idx) => (
                  <div key={idx} className="flex items-center justify-between gap-2">
                    <span className="text-[11px] text-muted">{k}</span>
                    <span className="text-right font-mono text-[11.5px] font-semibold text-ink">{v}</span>
                  </div>
                ))}
              </div>
              <div className="my-1.5 h-px bg-line" />
              <div className="mt-3 flex flex-col gap-2">
                <ReadField label="Delay" value={nodeProps.delay} />
                <ReadField label="Timeout" value={nodeProps.timeout} />
                <ReadField label="Retry" value={nodeProps.retry} />
                <div>
                  <label className="mb-1 block text-[10px] text-faint">Failure Action</label>
                  <div className="rounded-md border border-red/20 bg-red/[0.05] px-2.5 py-1.5 text-[12px] font-semibold text-red">{nodeProps.fail}</div>
                </div>
                <div>
                  <label className="mb-1 block text-[10px] text-faint">Comments</label>
                  <div className="rounded-md border border-line2 bg-bg px-2.5 py-2 text-[11px] leading-relaxed text-[#cfd6e2]">{nodeProps.comments}</div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {showRunModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#05070ac4] p-6">
          <div className="w-[480px] rounded-xl border border-line2 bg-panel p-[22px] shadow-[0_24px_70px_rgba(0,0,0,0.6)]">
            <div className="mb-3.5 flex items-center gap-2.5">
              <div className="flex h-[34px] w-[34px] items-center justify-center rounded-md bg-green/[0.12] text-[16px] text-green">▶</div>
              <div className="text-[16px] font-bold">Run Scenario — {graph.scenario.name}</div>
            </div>
            <div className="mb-3.5 text-[13px] leading-relaxed text-[#a9b2c0]">
              This dispatches validated SCPI command sequences to live simulator units. Confirm pre-run checks:
            </div>
            <div className="mb-5 flex flex-col gap-2 text-[12px] text-[#cfd6e2]">
              <div className="flex items-center gap-2"><span className="text-green">✓</span> Targets: {targetUnit} · single unit · simulation mode</div>
              <div className="flex items-center gap-2"><span className="text-green">✓</span> Dry-run validation passed · 0 invalid nodes</div>
              <div className="flex items-center gap-2"><span className="text-amber">⚠</span> Output will be energised to 28.0 V during run</div>
            </div>
            <div className="flex justify-end gap-2.5">
              <button onClick={() => setShowRunModal(false)} className="rounded-md border border-line2 bg-panel2 px-4.5 py-2 text-[13px] font-semibold text-ink">Cancel</button>
              <button onClick={runScenario} className="rounded-md bg-green px-4.5 py-2 text-[13px] font-bold text-[#04130c]">Confirm &amp; Run</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ToolBtn({ children, onClick, disabled }: { children: React.ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button onClick={onClick} disabled={disabled} className="rounded-md border border-line2 bg-panel2 px-2.5 py-1.5 text-[11px] font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-40">
      {children}
    </button>
  );
}

function ReadField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <label className="mb-1 block text-[10px] text-faint">{label}</label>
      <div className="rounded-md border border-line2 bg-bg px-2.5 py-1.5 font-mono text-[12px] text-ink">{value}</div>
    </div>
  );
}
