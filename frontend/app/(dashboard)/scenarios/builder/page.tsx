"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, SCENARIO_ID } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { usePageHeader } from "@/lib/header-context";
import { useUi } from "@/lib/ui-context";
import type { NodeState, NodeTypeSpec, Preset, ScenarioGraph, ScenarioNode, Unit } from "@/lib/types";

/** Matches data.CURVE_PRESET on the backend. */
const PRESET_SOURCE = "Stored preset";

const NODE_W = 178, NODE_H = 62;

/** Block accent by what the block does. */
const KIND_COLOR: Record<string, string> = {
  terminal: "#34d399", action: "#2dd4ee", flow: "#3b82f6",
  measure: "#5eead4", logic: "#fbbf24", danger: "#f87171",
};

/** Run-state colour code: green ready · yellow running · grey done · red error. */
const STATE_STYLE: Record<NodeState, { ring: string; dot: string; label: string }> = {
  ready:   { ring: "#34d399", dot: "#34d399", label: "ready" },
  running: { ring: "#fbbf24", dot: "#fbbf24", label: "running" },
  done:    { ring: "#5c6678", dot: "#5c6678", label: "done" },
  error:   { ring: "#f87171", dot: "#f87171", label: "error" },
  skipped: { ring: "#2c3543", dot: "#2c3543", label: "not taken" },
};

const LVL_COLOR: Record<string, string> = { ok: "#34d399", info: "#8a95a8", warn: "#fbbf24", err: "#f87171" };

function port(n: ScenarioNode, side: "in" | "out"): [number, number] {
  return side === "out" ? [n.x + NODE_W, n.y + NODE_H / 2] : [n.x, n.y + NODE_H / 2];
}

function edgePath(a: ScenarioNode, b: ScenarioNode) {
  const [x1, y1] = port(a, "out");
  const [x2, y2] = port(b, "in");
  const dx = Math.max(38, Math.abs(x2 - x1) / 2);
  return `M${x1},${y1} C ${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`;
}

function fmtDur(ms: number) {
  const s = Math.max(0, ms / 1000);
  return s >= 60 ? `${Math.floor(s / 60)}m ${String(Math.floor(s % 60)).padStart(2, "0")}s` : `${s.toFixed(1)}s`;
}

export default function ScenarioBuilderPage() {
  const { notify, ask } = useUi();
  const [graph, setGraph] = useState<ScenarioGraph | null>(null);
  usePageHeader("Scenario Builder", graph ? `${graph.scenario.name} · ${graph.scenario.version}` : "Loading…");
  const [selected, setSelected] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [showRunModal, setShowRunModal] = useState(false);
  const [dropHint, setDropHint] = useState(false);

  const canvasRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ id: string; dx: number; dy: number; moved: boolean } | null>(null);
  const [linking, setLinking] = useState<{ from: string; fail: boolean; x: number; y: number } | null>(null);
  const [localPos, setLocalPos] = useState<Record<string, { x: number; y: number }>>({});
  // keeps the newest positions reachable from the mouseup closure
  const posRef = useRef(localPos);
  posRef.current = localPos;
  // last elapsed the server reported, paired with the local instant it arrived
  const clock = useRef({ server: -1, local: 0 });

  const load = useCallback(async () => {
    try { setGraph(await api.scenario(SCENARIO_ID)); }
    catch (e) { notify(e instanceof Error ? e.message : "Could not load scenario"); }
  }, [notify]);

  useEffect(() => { load(); }, [load]);

  // While a run is live the graph is polled quickly so block colours, the
  // clock and the command history keep up with it.
  const run = graph?.run ?? null;
  const live = run?.status === "Running";
  const { data: liveRun } = usePoll(() => api.scenarioRun(SCENARIO_ID), live ? 600 : 4000, [live]);
  const runView = (liveRun && "id" in liveRun ? liveRun : run) ?? null;
  const isLive = runView?.status === "Running";

  const { data: units } = usePoll(() => api.units(), 10000);
  // Only enabled SAS presets can drive a solar-profile block.
  const { data: presetData } = usePoll(() => api.presets(), 15000);
  const sasPresets = (presetData?.presets ?? []).filter((p) => p.mode === "SAS" && p.enabled);
  const targetName = graph?.scenario.targetUnit || units?.find((u) => u.featured)?.name || units?.[0]?.name || "";
  const target = units?.find((u) => u.name === targetName);
  const targetActive = !!target && target.enabled && target.online;

  // a live clock so the elapsed readout ticks even between polls
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!isLive) return;
    const t = setInterval(() => setTick((n) => n + 1), 200);
    return () => clearInterval(t);
  }, [isLive]);

  if (!graph) return <div className="p-5 text-muted">Loading scenario…</div>;

  const nodes = graph.nodes.map((n) => ({ ...n, ...(localPos[n.id] ?? {}) }));
  const byId: Record<string, ScenarioNode> = {};
  nodes.forEach((n) => (byId[n.id] = n));
  const sel = selected ? byId[selected] : null;
  const selSpec = sel ? graph.nodeTypes.find((t) => t.type === sel.type) : null;
  const stateOf = (id: string): NodeState | null => (runView?.nodeStates?.[id] as NodeState) ?? null;
  /** "SAS-01" → "SAS-01 (@1)"; several channels are joined so a block reachable
   *  down paths that chose different equipment says so rather than picking one. */
  const labelFor = (names: string[]) =>
    names.map((n) => units?.find((u) => u.name === n)?.label ?? n).join(" / ");
  // Only worth labelling blocks with their channel when the graph uses more than one.
  const multiTarget = new Set(graph.nodes.flatMap((n) => n.runsOn ?? [])).size > 1;

  /** Zoom so the widest/tallest block still fits the visible canvas. */
  const fitToGraph = () => {
    const view = canvasRef.current?.parentElement;
    if (!view || !graph.nodes.length) return setZoom(1);
    const w = Math.max(...nodes.map((n) => n.x)) + NODE_W + 40;
    const h = Math.max(...nodes.map((n) => n.y)) + NODE_H + 40;
    const z = Math.min(view.clientWidth / w, view.clientHeight / h, 1.6);
    setZoom(Math.max(0.6, +z.toFixed(2)));
    view.scrollTo({ left: 0, top: 0 });
  };

  const canvasPoint = (e: { clientX: number; clientY: number }) => {
    const r = canvasRef.current?.getBoundingClientRect();
    if (!r) return { x: 0, y: 0 };
    return { x: (e.clientX - r.left) / zoom, y: (e.clientY - r.top) / zoom };
  };

  // ---- editing ------------------------------------------------------------
  const onNodeDown = (e: React.MouseEvent, n: ScenarioNode) => {
    if (isLive) return;
    e.preventDefault();
    e.stopPropagation();
    const p = canvasPoint(e);
    dragRef.current = { id: n.id, dx: p.x - n.x, dy: p.y - n.y, moved: false };
    const move = (ev: MouseEvent) => {
      const d = dragRef.current;
      if (!d) return;
      d.moved = true;
      const q = canvasPoint(ev);
      setLocalPos((prev) => ({ ...prev, [d.id]: { x: Math.max(0, Math.round(q.x - d.dx)), y: Math.max(0, Math.round(q.y - d.dy)) } }));
    };
    const up = async () => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      const d = dragRef.current;
      dragRef.current = null;
      if (!d) return;
      if (!d.moved) { setSelected(d.id); return; }
      const latest = posRef.current[d.id];
      if (latest) {
        try { await api.updateNode(SCENARIO_ID, d.id, { x: latest.x, y: latest.y }); }
        catch (e) { notify(e instanceof Error ? e.message : "Could not move block"); }
        load();
      }
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  };

  const startLink = (e: React.MouseEvent, from: string, fail: boolean) => {
    if (isLive) return;
    e.preventDefault();
    e.stopPropagation();
    const p = canvasPoint(e);
    setLinking({ from, fail, x: p.x, y: p.y });
    const move = (ev: MouseEvent) => {
      const q = canvasPoint(ev);
      setLinking((l) => (l ? { ...l, x: q.x, y: q.y } : l));
    };
    const up = async (ev: MouseEvent) => {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      const el = document.elementFromPoint(ev.clientX, ev.clientY);
      const dst = el?.closest("[data-node-id]")?.getAttribute("data-node-id");
      setLinking(null);
      if (!dst || dst === from) return;
      try {
        await api.addEdge(SCENARIO_ID, from, dst, fail);
        notify(`Connected ${byId[from]?.label} → ${byId[dst]?.label}${fail ? " (fail path)" : ""}`);
        load();
      } catch (err) {
        notify(err instanceof Error ? err.message : "Could not connect");
      }
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  };

  const onDropBlock = async (e: React.DragEvent) => {
    e.preventDefault();
    setDropHint(false);
    const type = e.dataTransfer.getData("application/x-sas-block");
    if (!type || isLive) return;
    const p = canvasPoint(e);
    try {
      await api.addNode(SCENARIO_ID, type, Math.max(0, Math.round(p.x - NODE_W / 2)), Math.max(0, Math.round(p.y - NODE_H / 2)));
      load();
    } catch (err) {
      notify(err instanceof Error ? err.message : "Could not add block");
    }
  };

  const saveParam = async (key: string, value: string) => {
    if (!sel) return;
    try {
      await api.updateNode(SCENARIO_ID, sel.id, { params: { ...sel.params, [key]: value } });
      load();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Value rejected");
    }
  };

  const removeNode = () => {
    if (!sel) return;
    ask({
      title: `Delete ${sel.label}`,
      message: "Removes this block and every connection to it.",
      confirmLabel: "Delete block", danger: true,
      onConfirm: async () => {
        try { await api.deleteNode(SCENARIO_ID, sel.id); setSelected(null); load(); }
        catch (e) { notify(e instanceof Error ? e.message : "Could not delete"); }
      },
    });
  };

  // ---- running ------------------------------------------------------------
  const startRun = async () => {
    setShowRunModal(false);
    try {
      await api.runScenario(SCENARIO_ID);
      notify("Scenario dispatched");
      load();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Could not start");
    }
  };

  const abort = async () => {
    try { const r = await api.abortScenario(SCENARIO_ID); notify(r.message); load(); }
    catch (e) { notify(e instanceof Error ? e.message : "Abort failed"); }
  };

  // Elapsed comes from the server and is carried forward locally between polls, so
  // the readout never depends on this browser's clock agreeing with the backend's.
  if (runView && runView.elapsedMs !== clock.current.server) {
    clock.current = { server: runView.elapsedMs, local: performance.now() };
  }
  const elapsed = !runView
    ? 0
    : runView.endedMs
      ? runView.elapsedMs
      : clock.current.server + (performance.now() - clock.current.local);

  const estimate = runView?.estMs || graph.estMs;
  const done = !!runView && runView.status !== "Running" && runView.status !== "Queued";
  const overrun = !done && elapsed > estimate;
  // The bar's time axis: the estimate while the run is live (stretching if it
  // overruns), the real duration once it has finished — so the step marks always
  // spread across exactly the span the bar is showing.
  const span = Math.max(done ? elapsed : Math.max(estimate, elapsed), 1);
  // A finished run reads 100%. A live one stops just short, so a bar that has
  // caught up with the estimate never looks like a run that has ended.
  const pct = done ? 100 : Math.min(99, (elapsed / span) * 100);
  const barColor = !runView || !done ? "#fbbf24"
    : runView.status === "Completed" ? "#34d399" : "#f87171";

  const canRun = targetActive && graph.validation.ok && !isLive;
  const runBlockedWhy = !targetActive
    ? `${targetName || "target"} is not active (enabled + reachable)`
    : !graph.validation.ok ? graph.validation.problems[0] : isLive ? "already running" : "";

  return (
    <div className="flex h-full flex-col">
      {/* toolbar */}
      <div className="flex h-[50px] flex-none items-center gap-3 border-b border-line bg-[#0e1117] px-4">
        <span className="text-[13px] font-bold">{graph.scenario.name}</span>
        <span className="font-mono text-[10px] text-faint">{graph.scenario.version}</span>
        <span className="rounded border border-amber/35 px-1.5 py-0.5 text-[10px] font-semibold text-amber">{graph.scenario.state}</span>
        {runView && (
          <span className="flex items-center gap-1.5 rounded border px-1.5 py-0.5 text-[10px] font-semibold"
            style={{ borderColor: isLive ? "#fbbf2455" : "#232a36", color: isLive ? "#fbbf24" : "#8a95a8" }}>
            {isLive && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber" />}
            {runView.id} · {runView.status}
          </span>
        )}
        <span className="font-mono text-[10px] text-faint">target {targetName || "—"}</span>
        <div className="flex-1" />
        <span title={canRun ? "" : runBlockedWhy}>
          <button onClick={() => setShowRunModal(true)} disabled={!canRun}
            className="rounded-md bg-green px-3.5 py-1.5 text-[11px] font-bold text-[#04130c] disabled:cursor-not-allowed disabled:bg-line2 disabled:text-faint">
            ▶ Run Scenario
          </button>
        </span>
        <button onClick={abort} disabled={!isLive}
          className="rounded-md border border-red/40 bg-red/10 px-3 py-1.5 text-[11px] font-semibold text-red disabled:cursor-not-allowed disabled:opacity-40">
          Abort
        </button>
      </div>

      {/* progress / time indicator — read-only, shows where the run is */}
      {runView && (
        <div className="flex-none border-b border-line bg-[#0c0f15] px-4 py-2">
          <div className="mb-1 flex items-center justify-between font-mono text-[10px] text-faint">
            <span>
              {isLive ? "running" : runView.status.toLowerCase()}
              {runView.currentNode && byId[runView.currentNode] ? ` · ${byId[runView.currentNode].label}` : ""}
              {isLive && ` · step ${runView.stepsDone + 1} of ${runView.stepsTotal}`}
              {done && ` · ${runView.stepsDone} of ${runView.stepsTotal} blocks run`}
            </span>
            <span style={{ color: overrun ? "#fbbf24" : undefined }}>
              {fmtDur(elapsed)} elapsed
              {done
                ? ` · finished ${runView.finished}`
                : overrun
                  ? ` · past the ~${fmtDur(estimate)} estimate`
                  : ` of ~${fmtDur(estimate)} estimated`}
            </span>
          </div>
          <div className="relative h-[6px] rounded-full bg-[#1b2230]">
            <div className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-200"
              style={{ width: `${pct}%`, background: barColor }} />
            {/* where each step actually ran, so the bar reads as a timeline */}
            {runView.events.map((ev, i) =>
              ev.atMs === null || !byId[ev.node] ? null : (
                <span key={i} title={`${byId[ev.node].label} · ${fmtDur(ev.atMs)}`}
                  className="absolute top-[-2px] h-[10px] w-[2px] rounded-full"
                  style={{
                    left: `${Math.min(100, (ev.atMs / span) * 100)}%`,
                    background: ev.lvl === "err" ? "#f87171" : "#ffffff55",
                  }} />
              ))}
          </div>
          <div className="mt-1 flex items-center gap-3 font-mono text-[9px] text-faint">
            {(["ready", "running", "done", "error"] as NodeState[]).map((s) => (
              <span key={s} className="flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: STATE_STYLE[s].dot }} />{STATE_STYLE[s].label}
              </span>
            ))}
            <span className="flex items-center gap-1">
              <span className="h-[8px] w-[2px] rounded-full bg-[#ffffff55]" />each step
            </span>
          </div>
        </div>
      )}

      <div className="flex min-h-0 min-w-0 flex-1">
        {/* palette */}
        <div className="w-[190px] flex-none overflow-auto border-r border-line bg-[#0e1117] p-2.5">
          <div className="mb-1 ml-1 text-[9.5px] uppercase tracking-wider text-faint">Block Palette</div>
          <div className="mb-2 ml-1 text-[10px] leading-snug text-faint">Drag a block onto the canvas.</div>
          {graph.nodeTypes.map((t) => (
            <div key={t.type} draggable={!isLive}
              onDragStart={(e) => { e.dataTransfer.setData("application/x-sas-block", t.type); e.dataTransfer.effectAllowed = "copy"; }}
              title={t.help}
              className="mb-1 flex cursor-grab items-center gap-2 rounded-md border border-line2 bg-panel px-2.5 py-2 text-[11.5px] text-[#cfd6e2] hover:border-cyan/40 active:cursor-grabbing">
              <span className="h-1.5 w-1.5 flex-none rounded-full" style={{ background: KIND_COLOR[t.kind] }} />
              {t.label}
            </div>
          ))}
        </div>

        {/* canvas */}
        <div className="relative flex min-w-0 flex-1 flex-col">
          <div
            className="relative min-h-0 flex-1 overflow-auto"
            style={{
              backgroundColor: "#0c0f15",
              backgroundImage: "linear-gradient(#ffffff08 1px,transparent 1px),linear-gradient(90deg,#ffffff08 1px,transparent 1px)",
              backgroundSize: "22px 22px",
              outline: dropHint ? "2px dashed #2dd4ee66" : "none",
              outlineOffset: -6,
            }}
            onDragOver={(e) => { e.preventDefault(); setDropHint(true); }}
            onDragLeave={() => setDropHint(false)}
            onDrop={onDropBlock}
            onMouseDown={() => setSelected(null)}
          >
            <div ref={canvasRef} className="relative" style={{ transformOrigin: "0 0", transform: `scale(${zoom})`, width: 1400, height: 560 }}>
              <svg className="absolute inset-0" width={1400} height={560} style={{ overflow: "visible", pointerEvents: "none" }}>
                <defs>
                  <marker id="ah" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z" fill="#2dd4ee" /></marker>
                  <marker id="ah-fail" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0,0 L9,4.5 L0,9 z" fill="#f87171" /></marker>
                </defs>
                {graph.edges.map((e) => {
                  const a = byId[e.from], b = byId[e.to];
                  if (!a || !b) return null;
                  const active = isLive && runView?.currentNode === e.to;
                  return (
                    <g key={e.id} style={{ pointerEvents: "stroke" }}>
                      <path d={edgePath(a, b)} fill="none" stroke="transparent" strokeWidth={14}
                        style={{ cursor: isLive ? "default" : "pointer" }}
                        onClick={async () => {
                          if (isLive) return;
                          try { await api.deleteEdge(SCENARIO_ID, e.id); notify("Connection removed"); load(); }
                          catch (err) { notify(err instanceof Error ? err.message : "Could not remove"); }
                        }}>
                        <title>{e.fail ? "fail path" : "next step"} — click to remove</title>
                      </path>
                      <path d={edgePath(a, b)} fill="none" stroke={e.fail ? "#f87171" : "#2dd4ee"}
                        strokeWidth={active ? 3 : 2} strokeDasharray={e.fail ? "5 4" : "0"}
                        opacity={active ? 1 : 0.85} markerEnd={`url(#${e.fail ? "ah-fail" : "ah"})`} />
                    </g>
                  );
                })}
                {linking && byId[linking.from] && (
                  <path d={`M${port(byId[linking.from], "out")[0]},${port(byId[linking.from], "out")[1]} L${linking.x},${linking.y}`}
                    fill="none" stroke={linking.fail ? "#f87171" : "#2dd4ee"} strokeWidth={2} strokeDasharray="4 4" />
                )}
              </svg>

              {nodes.map((n) => {
                const color = KIND_COLOR[n.kind] ?? "#2dd4ee";
                const st = stateOf(n.id);
                const style = st ? STATE_STYLE[st] : null;
                const isSel = n.id === selected;
                const isCurrent = runView?.currentNode === n.id;
                return (
                  <div key={n.id} data-node-id={n.id}
                    onMouseDown={(e) => onNodeDown(e, n)}
                    className="absolute select-none rounded-md px-2.5 pb-2.5 pt-2"
                    style={{
                      left: n.x, top: n.y, width: NODE_W, minHeight: NODE_H,
                      // whatever you are working on sits above anything overlapping it
                      zIndex: isSel || isCurrent ? 2 : 1,
                      cursor: isLive ? "default" : "grab",
                      background: n.kind === "danger" ? "#1f1216" : "#1a1f29",
                      border: `1.5px solid ${style ? style.ring : isSel ? color : color + "66"}`,
                      boxShadow: isCurrent
                        ? `0 0 0 3px #fbbf2444, 0 8px 22px rgba(0,0,0,.5)`
                        : isSel ? `0 0 0 3px ${color}33, 0 8px 22px rgba(0,0,0,.5)` : "0 4px 14px rgba(0,0,0,.45)",
                      opacity: st === "skipped" ? 0.45 : 1,
                    }}>
                    <div className="absolute right-2 top-2 flex items-center gap-1">
                      {st && <span className="font-mono text-[8px]" style={{ color: style!.dot }}>{style!.label}</span>}
                      <span className="h-1.5 w-1.5 rounded-full"
                        style={{ background: style ? style.dot : color, boxShadow: `0 0 7px ${style ? style.dot : color}` }} />
                    </div>
                    <div className="mb-1 inline-block rounded px-1.5 py-0.5 font-mono text-[8.5px] font-semibold tracking-wider"
                      style={{ color, background: color + "1f" }}>{n.badge}</div>
                    <div className="text-[12.5px] font-semibold leading-tight text-ink">{n.label}</div>
                    {n.sub && <div className="mt-0.5 font-mono text-[10px] text-muted">{n.sub}</div>}
                    {multiTarget && n.type !== "target" && !!n.runsOn?.length && (
                      <div className="mt-0.5 font-mono text-[9px] text-faint">on {labelFor(n.runsOn)}</div>
                    )}

                    {/* output ports: drag one onto another block to connect */}
                    {!isLive && n.type !== "end" && n.type !== "shutdown" && (
                      <>
                        <span onMouseDown={(e) => startLink(e, n.id, false)} title="Drag to the next block"
                          className="absolute h-3 w-3 cursor-crosshair rounded-full border-2"
                          style={{ right: -7, top: NODE_H / 2 - 6, borderColor: "#2dd4ee", background: "#0e1117" }} />
                        {n.type === "threshold" && (
                          <span onMouseDown={(e) => startLink(e, n.id, true)} title="Drag to the block that runs when the check fails"
                            className="absolute h-3 w-3 cursor-crosshair rounded-full border-2"
                            style={{ right: -7, bottom: -7, borderColor: "#f87171", background: "#0e1117" }} />
                        )}
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* zoom */}
          <div className="absolute bottom-[152px] left-4 flex items-center gap-1.5 rounded-md border border-line bg-panel p-1.5">
            <div onClick={() => setZoom((z) => Math.max(0.6, +(z - 0.1).toFixed(2)))} className="flex h-[26px] w-[26px] cursor-pointer items-center justify-center rounded-md bg-panel2 text-[15px] text-[#cfd6e2]">−</div>
            <span className="w-[42px] text-center font-mono text-[11px] text-muted">{Math.round(zoom * 100)}%</span>
            <div onClick={() => setZoom((z) => Math.min(1.6, +(z + 0.1).toFixed(2)))} className="flex h-[26px] w-[26px] cursor-pointer items-center justify-center rounded-md bg-panel2 text-[15px] text-[#cfd6e2]">+</div>
            <div onClick={fitToGraph} title="Zoom so every block is visible"
              className="flex h-[26px] cursor-pointer items-center rounded-md bg-panel2 px-2.5 text-[10px] text-muted">Fit</div>
          </div>

          {/* command history for this run */}
          <div className="h-[150px] flex-none overflow-auto border-t border-line bg-[#0e1117]">
            <div className="sticky top-0 flex items-center gap-3 border-b border-line bg-[#0e1117] px-3 py-1.5">
              <span className="text-[11px] font-semibold">Command history{runView ? ` · ${runView.id}` : ""}</span>
              <span className="font-mono text-[9.5px] text-faint">{runView?.events.length ?? 0} entries · every command this run sent</span>
              <div className="flex-1" />
              {runView && (
                <>
                  <a href={api.runCsvUrl(runView.id)} download
                    className="rounded border border-line2 px-2 py-0.5 font-mono text-[9.5px] text-[#cfd6e2] hover:border-cyan/50 hover:text-cyan">
                    ↓ CSV · every step
                  </a>
                  <a href={api.runCsvUrl(runView.id, true)} download
                    className="rounded border border-line2 px-2 py-0.5 font-mono text-[9.5px] text-[#cfd6e2] hover:border-cyan/50 hover:text-cyan">
                    ↓ CSV · measurements
                  </a>
                </>
              )}
            </div>
            {(runView?.events ?? []).slice().reverse().map((ev, i) => (
              <div key={i} className="grid items-baseline gap-2 border-b border-[#161b24] px-3 py-1 font-mono text-[10.5px]"
                style={{ gridTemplateColumns: `62px 120px ${multiTarget ? "92px " : ""}1fr 190px 52px` }}>
                <span className="text-faint">{ev.t}</span>
                <span className="truncate" style={{ color: LVL_COLOR[ev.lvl] }}>{byId[ev.node]?.label ?? ev.node}</span>
                {multiTarget && <span className="truncate text-faint">{labelFor(ev.unit ? [ev.unit] : [])}</span>}
                <span className="truncate text-[#cfd6e2]">{ev.m}</span>
                <span className="truncate text-cyan" title={ev.scpi}>{ev.scpi}</span>
                <span className="text-right text-faint">{ev.lat ? `${ev.lat} ms` : ""}</span>
              </div>
            ))}
            {!runView?.events.length && (
              <div className="px-3 py-4 text-center text-[11px] text-faint">No run yet — press Run Scenario to dispatch this graph.</div>
            )}
          </div>
        </div>

        {/* inspector */}
        <div className="w-[300px] flex-none overflow-auto border-l border-line bg-[#0e1117] p-3.5">
          <div className="mb-2.5 text-[10px] uppercase tracking-wider text-faint">Block Settings</div>
          {!sel && (
            <div className="rounded-[9px] border border-dashed border-line2 p-4 text-[11.5px] leading-relaxed text-faint">
              Select a block to edit what it does. Drag a block from the palette to add one, drag the ○ on a block&apos;s right edge onto another block to connect them, and click a connection to remove it.
            </div>
          )}
          {sel && selSpec && (
            <div className="rounded-[9px] border border-line bg-panel p-3.5">
              <div className="mb-0.5 text-[14px] font-bold">{sel.label}</div>
              <div className="mb-3 text-[11px] text-muted">
                {selSpec.badge}
                {sel.type === "target"
                  ? " · changes the channel for the steps after it"
                  : ` · runs on ${labelFor(sel.runsOn) || targetName || "—"}`}
              </div>

              {selSpec.params.length === 0 && (
                <div className="mb-3 rounded-md border border-line2 bg-bg px-2.5 py-2 text-[11px] text-faint">
                  This block has no settings.
                </div>
              )}
              <div className="mb-3 flex flex-col gap-2.5">
                {/* a param marked `only` belongs to one source — hide the other set */}
                {selSpec.params
                  .filter((p) => !p.only || p.only === sel.params.source)
                  .map((p) => (
                    <ParamField key={p.key} spec={p} value={String(sel.params[p.key] ?? "")}
                      presets={sasPresets} units={units ?? []} disabled={isLive}
                      onCommit={(v) => saveParam(p.key, v)} />
                  ))}
              </div>

              {sel.type === "sas" && sel.params.source === PRESET_SOURCE && (
                <div className="mb-3 rounded-md border border-line2 bg-bg px-2.5 py-2 text-[10.5px] leading-relaxed text-faint">
                  Values are read from the preset when the block runs, so editing the preset changes every
                  scenario that points at it.{" "}
                  <a href="/config" className="text-cyan underline">Manage presets</a>
                </div>
              )}

              {stateOf(sel.id) && (
                <div className="mb-3 rounded-md border px-2.5 py-1.5 text-[11px] font-semibold"
                  style={{ borderColor: STATE_STYLE[stateOf(sel.id)!].ring + "55", color: STATE_STYLE[stateOf(sel.id)!].dot }}>
                  last run · {STATE_STYLE[stateOf(sel.id)!].label}
                </div>
              )}

              <div className="mb-3 rounded-md border border-line2 bg-bg px-2.5 py-2 text-[10.5px] leading-relaxed text-[#cfd6e2]">
                {selSpec.help}
              </div>

              <div className="flex gap-2">
                <button onClick={removeNode} disabled={isLive || sel.type === "start"}
                  className="rounded border border-red/40 bg-red/10 px-2.5 py-1 text-[10.5px] font-semibold text-red disabled:cursor-not-allowed disabled:opacity-40">
                  Delete block
                </button>
              </div>
            </div>
          )}

          {!graph.validation.ok && (
            <div className="mt-3 rounded-md border border-red/30 bg-red/[0.06] p-2.5">
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-red">Not runnable yet</div>
              {graph.validation.problems.map((p, i) => (
                <div key={i} className="mb-1 text-[10.5px] leading-snug text-red">· {p}</div>
              ))}
            </div>
          )}

          {/* worth reading, but the run is allowed */}
          {!!graph.validation.warnings?.length && (
            <div className="mt-3 rounded-md border border-amber/30 bg-amber/[0.06] p-2.5">
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-amber">Check before running</div>
              {graph.validation.warnings.map((p, i) => (
                <div key={i} className="mb-1 text-[10.5px] leading-snug text-amber">· {p}</div>
              ))}
            </div>
          )}
        </div>
      </div>

      {showRunModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#05070ac4] p-6">
          <div className="w-[500px] rounded-xl border border-line2 bg-panel p-[22px] shadow-[0_24px_70px_rgba(0,0,0,0.6)]">
            <div className="mb-3.5 flex items-center gap-2.5">
              <div className="flex h-[34px] w-[34px] items-center justify-center rounded-md bg-green/[0.12] text-[16px] text-green">▶</div>
              <div className="text-[16px] font-bold">Run {graph.scenario.name}</div>
            </div>
            <div className="mb-3.5 text-[13px] leading-relaxed text-[#a9b2c0]">
              Each block is dispatched to <b className="text-ink">{targetName}</b> as real SCPI, confirmed by readback and recorded in the audit log. The canvas colours each block as it runs.
            </div>
            <div className="mb-5 flex flex-col gap-2 font-mono text-[11.5px] text-[#cfd6e2]">
              <div>· {graph.nodes.length} blocks · estimated {fmtDur(graph.estMs)}</div>
              <div>· validation passed · {graph.edges.filter((e) => e.fail).length} fail path(s)</div>
              <div className="text-amber">⚠ the output will be energised during this run</div>
            </div>
            <div className="flex justify-end gap-2.5">
              <button onClick={() => setShowRunModal(false)} className="rounded-md border border-line2 bg-panel2 px-4.5 py-2 text-[13px] font-semibold text-ink">Cancel</button>
              <button onClick={startRun} className="rounded-md bg-green px-4.5 py-2 text-[13px] font-bold text-[#04130c]">Confirm &amp; Run</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ParamField({ spec, value, presets, units, disabled, onCommit }: {
  spec: NodeTypeSpec["params"][number]; value: string; presets: Preset[]; units: Unit[];
  disabled: boolean; onCommit: (v: string) => void;
}) {
  const [draft, setDraft] = useState(value);
  useEffect(() => { setDraft(value); }, [value]);

  if (spec.type === "unit") {
    // Only channels that are enabled can be dispatched to; a disabled one is still
    // listed when it is the current choice, so the block does not silently change.
    const choices = units.filter((u) => u.enabled || u.name === value);
    return (
      <div>
        <label className="mb-1 block text-[10px] text-faint">{spec.label}</label>
        <select value={value} disabled={disabled} onChange={(e) => onCommit(e.target.value)}
          className="w-full rounded-md border bg-bg px-2.5 py-1.5 font-mono text-[12px] text-ink disabled:opacity-50"
          style={{ borderColor: value ? "#232a36" : "#f8717188" }}>
          <option value="">— choose an instrument and channel —</option>
          {choices.map((u) => (
            <option key={u.name} value={u.name}>
              {u.label}{u.online ? "" : "  · unreachable"}{u.enabled ? "" : "  · disabled"}
            </option>
          ))}
        </select>
        {!choices.length && (
          <div className="mt-1 text-[10px] leading-snug text-amber">
            No enabled channels — add or enable one in Configuration.
          </div>
        )}
      </div>
    );
  }

  if (spec.type === "preset") {
    return (
      <div>
        <label className="mb-1 block text-[10px] text-faint">{spec.label}</label>
        <select value={value} disabled={disabled} onChange={(e) => onCommit(e.target.value)}
          className="w-full rounded-md border bg-bg px-2.5 py-1.5 text-[12px] text-ink disabled:opacity-50"
          style={{ borderColor: value === "0" ? "#f8717188" : "#232a36" }}>
          <option value="0">— choose a stored SAS preset —</option>
          {presets.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} · Vmp {p.vmp}V / Imp {p.imp}A
            </option>
          ))}
        </select>
        {!presets.length && (
          <div className="mt-1 text-[10px] leading-snug text-amber">
            No enabled SAS presets stored yet — add one in Configuration.
          </div>
        )}
      </div>
    );
  }

  if (spec.type === "select") {
    return (
      <div>
        <label className="mb-1 block text-[10px] text-faint">{spec.label}</label>
        <select value={value} disabled={disabled} onChange={(e) => onCommit(e.target.value)}
          className="w-full rounded-md border border-line2 bg-bg px-2.5 py-1.5 font-mono text-[12px] text-ink disabled:opacity-50">
          {spec.options?.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      </div>
    );
  }
  const dirty = draft !== value;
  return (
    <div>
      <label className="mb-1 block text-[10px] text-faint">
        {spec.label}{spec.unit ? ` (${spec.unit})` : ""}
        {spec.min !== undefined && spec.max !== undefined && (
          <span className="text-faint/60"> · {spec.min}–{spec.max}</span>
        )}
      </label>
      <div className="flex gap-1.5">
        <input value={draft} disabled={disabled} inputMode="decimal"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") onCommit(draft); if (e.key === "Escape") setDraft(value); }}
          onBlur={() => dirty && onCommit(draft)}
          className="w-full rounded-md border bg-bg px-2.5 py-1.5 font-mono text-[12px] text-ink disabled:opacity-50"
          style={{ borderColor: dirty ? "#fbbf2477" : "#232a36" }} />
        {dirty && !disabled && (
          <button onClick={() => onCommit(draft)}
            className="rounded-md border border-cyan/50 bg-cyan/10 px-2 text-[10px] font-semibold text-cyan">Set</button>
        )}
      </div>
    </div>
  );
}
