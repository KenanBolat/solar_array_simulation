"use client";

import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  addEdge,
  Background,
  type Connection,
  Controls,
  type Edge,
  Handle,
  MiniMap,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  useReactFlow,
} from "@xyflow/react";
import { CheckCircle2, FlaskConical, Play, Plus, Save, XCircle } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { Panel, PanelHeader, Badge, Button, Field, Select } from "@/components/ui/kit";
import {
  useCreateScenario,
  useDevices,
  useRunScenario,
  useScenario,
  useScenarios,
  useValidateScenario,
} from "@/lib/hooks";
import { PALETTE, PALETTE_BY_TYPE } from "@/lib/palette";
import type { ValidationResult } from "@/lib/types";

let keyCounter = 1000;
const nextKey = (t: string) => `${t}_${keyCounter++}`;

// --- Custom node ------------------------------------------------------------

function StepNode({ data, selected }: NodeProps) {
  const meta = PALETTE_BY_TYPE[(data as { ntype: string }).ntype];
  const color = meta?.color ?? "var(--color-ink-faint)";
  const isTerminal = (data as { ntype: string }).ntype === "start" ||
    (data as { ntype: string }).ntype === "end";
  return (
    <div
      className="min-w-[150px] rounded-md border bg-[var(--color-surface-2)] px-3 py-2 text-xs shadow-sm"
      style={{
        borderColor: selected ? "var(--color-active)" : "var(--color-hairline-strong)",
        boxShadow: selected ? "0 0 0 1px var(--color-active)" : undefined,
      }}
    >
      {(data as { ntype: string }).ntype !== "start" ? (
        <Handle type="target" position={Position.Left} style={{ background: color }} />
      ) : null}
      <div className="flex items-center gap-2">
        <span className="status-dot" style={{ color, background: color }} />
        <span className="font-semibold text-[var(--color-ink)]">
          {(data as { label: string }).label}
        </span>
      </div>
      <div className="mt-0.5 text-[10px] uppercase tracking-wide text-[var(--color-ink-faint)]">
        {(data as { ntype: string }).ntype.replace(/_/g, " ")}
      </div>
      {!isTerminal ? (
        <Handle type="source" position={Position.Right} style={{ background: color }} />
      ) : (data as { ntype: string }).ntype === "start" ? (
        <Handle type="source" position={Position.Right} style={{ background: color }} />
      ) : null}
    </div>
  );
}

const nodeTypes = { step: StepNode };

// --- Builder ----------------------------------------------------------------

function BuilderInner() {
  const scenarios = useScenarios();
  const [scenarioId, setScenarioId] = useState("");
  const detail = useScenario(scenarioId);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [dirty, setDirty] = useState(false);
  const [dropActive, setDropActive] = useState(false);

  // Translates a viewport pointer position into canvas coordinates so a
  // dropped node lands exactly where the operator released it.
  const { screenToFlowPosition } = useReactFlow();

  // pick the first scenario by default
  useEffect(() => {
    if (!scenarioId && scenarios.data && scenarios.data.length > 0) {
      setScenarioId(scenarios.data[0].id);
    }
  }, [scenarios.data, scenarioId]);

  // load graph from the selected scenario
  useEffect(() => {
    if (!detail.data) return;
    setNodes(
      detail.data.nodes.map((n) => ({
        id: n.node_key,
        type: "step",
        position: { x: n.x, y: n.y },
        data: { label: n.label || n.type, ntype: n.type, config: n.config },
      }))
    );
    setEdges(
      detail.data.edges.map((e) => ({
        id: e.edge_key,
        source: e.source,
        target: e.target,
        animated: true,
        style: { stroke: "var(--color-hairline-strong)" },
      }))
    );
    setValidation(null);
    setDirty(false);
  }, [detail.data, setNodes, setEdges]);

  const onConnect = useCallback(
    (c: Connection) => {
      setEdges((eds) => addEdge({ ...c, animated: true, id: `e_${keyCounter++}` }, eds));
      setDirty(true);
    },
    [setEdges]
  );

  // `position` is supplied when the node arrives by drag-and-drop; clicking a
  // palette entry falls back to a scattered position. `connectFrom` chains the
  // new node onto the current selection so dropping steps in order builds a
  // runnable sequence without hand-wiring every edge.
  const addNode = useCallback(
    (type: string, position?: { x: number; y: number }, connectFrom?: string | null) => {
      const meta = PALETTE_BY_TYPE[type];
      const id = nextKey(type);
      setNodes((nds) => [
        ...nds,
        {
          id,
          type: "step",
          position: position ?? { x: 120 + Math.random() * 280, y: 80 + Math.random() * 260 },
          data: {
            label: meta?.label ?? type,
            ntype: type,
            config: { ...(meta?.defaultConfig ?? {}) },
          },
        },
      ]);
      if (connectFrom && connectFrom !== id && type !== "start") {
        setEdges((eds) =>
          addEdge(
            {
              source: connectFrom,
              target: id,
              sourceHandle: null,
              targetHandle: null,
              animated: true,
              id: `e_${keyCounter++}`,
            },
            eds
          )
        );
      }
      setSelectedId(id);
      setDirty(true);
    },
    [setNodes, setEdges]
  );

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedId) ?? null,
    [nodes, selectedId]
  );

  function updateSelectedConfig(config: Record<string, unknown>, label?: string) {
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedId
          ? { ...n, data: { ...n.data, config, ...(label !== undefined ? { label } : {}) } }
          : n
      )
    );
    setDirty(true);
  }

  // serialise graph back to API shape
  function serialise() {
    return {
      nodes: nodes.map((n) => ({
        node_key: n.id,
        type: (n.data as { ntype: string }).ntype,
        label: (n.data as { label: string }).label,
        x: n.position.x,
        y: n.position.y,
        config: (n.data as { config?: Record<string, unknown> }).config ?? {},
      })),
      edges: edges.map((e) => ({
        edge_key: e.id,
        source: e.source,
        target: e.target,
        label: "",
      })),
    };
  }

  const create = useCreateScenario();
  const validate = useValidateScenario(scenarioId);

  function onSaveAsNew() {
    const g = serialise();
    const name = `${detail.data?.name ?? "Scenario"} (copy ${new Date().toISOString().slice(11, 19)})`;
    create.mutate(
      { name, description: detail.data?.description ?? "", nodes: g.nodes, edges: g.edges },
      {
        onSuccess: (s) => {
          setScenarioId(s.id);
          setDirty(false);
        },
      }
    );
  }

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Scenario Builder"
        subtitle="Compose, validate and run automated test sequences"
        actions={
          <div className="flex items-center gap-2">
            <Select
              value={scenarioId}
              onChange={(e) => setScenarioId(e.target.value)}
              className="w-56"
            >
              {(scenarios.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
            <Button variant="outline" size="sm" onClick={onSaveAsNew} disabled={create.isPending}>
              <Save size={14} /> Save as new
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={() => validate.mutate(undefined, { onSuccess: setValidation })}
              disabled={!scenarioId || dirty}
              title={dirty ? "Save changes before validating" : undefined}
            >
              <CheckCircle2 size={14} /> Validate
            </Button>
          </div>
        }
      />

      <div className="flex min-h-0 flex-1">
        {/* Palette */}
        <div className="w-52 shrink-0 overflow-y-auto border-r border-[var(--color-hairline)] bg-[var(--color-surface)] p-3">
          <div className="eyebrow mb-2">Node palette</div>
          {(["flow", "action", "logic", "meta"] as const).map((group) => (
            <div key={group} className="mb-3">
              <div className="mb-1 text-[10px] uppercase tracking-wide text-[var(--color-ink-faint)]">
                {group}
              </div>
              <div className="space-y-1">
                {PALETTE.filter((p) => p.group === group).map((p) => (
                  <button
                    key={p.type}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData("application/sas-node", p.type);
                      e.dataTransfer.effectAllowed = "move";
                    }}
                    onClick={() => addNode(p.type, undefined, selectedId)}
                    title={`Drag onto the canvas, or click to append to the selected step`}
                    className="flex w-full cursor-grab items-center gap-2 rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] px-2.5 py-1.5 text-left text-xs text-[var(--color-ink-dim)] transition-colors hover:border-[var(--color-hairline-strong)] hover:text-[var(--color-ink)] active:cursor-grabbing"
                  >
                    <span className="status-dot" style={{ color: p.color, background: p.color }} />
                    {p.label}
                    <Plus size={11} className="ml-auto text-[var(--color-ink-faint)]" />
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Canvas */}
        <div
          className="relative min-w-0 flex-1"
          onDragEnter={() => setDropActive(true)}
          onDragOver={(e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
          }}
          onDragLeave={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget as globalThis.Node | null)) {
              setDropActive(false);
            }
          }}
          onDrop={(e) => {
            e.preventDefault();
            setDropActive(false);
            const type = e.dataTransfer.getData("application/sas-node");
            if (!type || !PALETTE_BY_TYPE[type]) return;
            addNode(type, screenToFlowPosition({ x: e.clientX, y: e.clientY }), selectedId);
          }}
        >
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={(c) => {
              onNodesChange(c);
              if (c.some((x) => x.type === "position" || x.type === "remove")) setDirty(true);
            }}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, n) => setSelectedId(n.id)}
            onPaneClick={() => setSelectedId(null)}
            nodeTypes={nodeTypes}
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#232e3d" gap={20} />
            <Controls />
            <MiniMap
              pannable
              zoomable
              nodeColor={(n) => PALETTE_BY_TYPE[(n.data as { ntype: string }).ntype]?.color ?? "#555"}
              maskColor="rgba(9,13,19,0.7)"
            />
          </ReactFlow>

          {validation ? (
            <ValidationToast result={validation} onClose={() => setValidation(null)} />
          ) : null}
          {dirty ? (
            <div className="absolute left-3 top-3 z-10">
              <Badge color="var(--color-warning)">Unsaved changes</Badge>
            </div>
          ) : null}
          {dropActive ? (
            <div className="pointer-events-none absolute inset-0 z-10 flex items-start justify-center rounded-sm border-2 border-dashed border-[var(--color-active)] bg-[color-mix(in_srgb,var(--color-active)_6%,transparent)]">
              <span className="mt-4 rounded-md border border-[var(--color-active)] bg-[var(--color-surface-2)] px-3 py-1.5 text-xs font-semibold text-[var(--color-active)]">
                Drop to place step
                {selectedId ? " — will chain from selection" : ""}
              </span>
            </div>
          ) : null}
        </div>

        {/* Properties + run */}
        <div className="w-72 shrink-0 overflow-y-auto border-l border-[var(--color-hairline)] bg-[var(--color-surface)]">
          <PropertiesPanel
            node={selectedNode}
            onChange={updateSelectedConfig}
            onDelete={() => {
              setNodes((nds) => nds.filter((n) => n.id !== selectedId));
              setEdges((eds) => eds.filter((e) => e.source !== selectedId && e.target !== selectedId));
              setSelectedId(null);
              setDirty(true);
            }}
          />
          <RunPanel scenarioId={scenarioId} dirty={dirty} />
        </div>
      </div>
    </div>
  );
}

// --- Properties panel -------------------------------------------------------

function PropertiesPanel({
  node,
  onChange,
  onDelete,
}: {
  node: Node | null;
  onChange: (config: Record<string, unknown>, label?: string) => void;
  onDelete: () => void;
}) {
  if (!node) {
    return (
      <div className="p-4">
        <div className="eyebrow mb-1">Properties</div>
        <p className="text-xs text-[var(--color-ink-faint)]">
          Drag a step from the palette onto the canvas to place it. With a step
          selected, the next one you add is chained onto it automatically. Drag
          from a node’s right handle to another node’s left handle to wire edges
          by hand.
        </p>
      </div>
    );
  }
  const ntype = (node.data as { ntype: string }).ntype;
  const label = (node.data as { label: string }).label;
  const config = ((node.data as { config?: Record<string, unknown> }).config ?? {}) as Record<
    string,
    unknown
  >;

  const set = (k: string, v: unknown) => onChange({ ...config, [k]: v });

  return (
    <div className="border-b border-[var(--color-hairline)] p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="eyebrow">Properties</div>
        <Badge color={PALETTE_BY_TYPE[ntype]?.color ?? "var(--color-ink-faint)"}>{ntype}</Badge>
      </div>

      <div className="space-y-3">
        <Field label="Label">
          <input
            value={label}
            onChange={(e) => onChange(config, e.target.value)}
            className="h-9 rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] px-3 text-sm text-[var(--color-ink)] focus-visible:border-[var(--color-active)]"
          />
        </Field>

        {ntype === "wait" ? (
          <Field label="Seconds" hint="capped at 30s per wait">
            <input
              type="number"
              value={(config.seconds as number) ?? 3}
              onChange={(e) => set("seconds", parseFloat(e.target.value))}
              className="readout h-9 rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] px-3 text-sm text-[var(--color-ink)]"
            />
          </Field>
        ) : null}

        {ntype === "set_output_state" ? (
          <Field label="Output">
            <Select
              value={String(config.enabled ?? true)}
              onChange={(e) => set("enabled", e.target.value === "true")}
            >
              <option value="true">Enable</option>
              <option value="false">Disable</option>
            </Select>
          </Field>
        ) : null}

        {ntype === "repeat" ? (
          <Field label="Max iterations" hint="bounded; required to be positive">
            <input
              type="number"
              value={(config.max_iterations as number) ?? 5}
              onChange={(e) => set("max_iterations", parseInt(e.target.value, 10))}
              className="readout h-9 rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] px-3 text-sm text-[var(--color-ink)]"
            />
          </Field>
        ) : null}

        {ntype === "threshold_check" || ntype === "condition" ? (
          <div className="grid grid-cols-3 gap-2">
            <Field label="Field">
              <Select value={(config.field as string) ?? "power_w"} onChange={(e) => set("field", e.target.value)}>
                <option value="power_w">power_w</option>
                <option value="voltage_v">voltage_v</option>
                <option value="current_a">current_a</option>
              </Select>
            </Field>
            <Field label="Op">
              <Select value={(config.op as string) ?? ">="} onChange={(e) => set("op", e.target.value)}>
                <option value=">=">≥</option>
                <option value="<=">≤</option>
                <option value="==">=</option>
              </Select>
            </Field>
            <Field label="Value">
              <input
                type="number"
                value={(config.value as number) ?? 0}
                onChange={(e) => set("value", parseFloat(e.target.value))}
                className="readout h-9 w-full rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] px-2 text-sm text-[var(--color-ink)]"
              />
            </Field>
          </div>
        ) : null}

        {ntype === "send_command" ? (
          <Field label="Template id" hint="must be a known command template">
            <input
              value={(config.template_id as string) ?? ""}
              onChange={(e) => set("template_id", e.target.value)}
              className="readout h-9 rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] px-3 text-sm text-[var(--color-ink)]"
            />
          </Field>
        ) : null}

        {ntype === "apply_profile" ? (
          <Field label="Profile name">
            <input
              value={(config.profile as string) ?? ""}
              onChange={(e) => set("profile", e.target.value)}
              className="h-9 rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] px-3 text-sm text-[var(--color-ink)]"
            />
          </Field>
        ) : null}

        {ntype === "notification" ? (
          <Field label="Message">
            <input
              value={(config.message as string) ?? ""}
              onChange={(e) => set("message", e.target.value)}
              className="h-9 rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] px-3 text-sm text-[var(--color-ink)]"
            />
          </Field>
        ) : null}

        <Button variant="outline" size="sm" className="w-full" onClick={onDelete}>
          Delete node
        </Button>
      </div>
    </div>
  );
}

// --- Run panel --------------------------------------------------------------

function RunPanel({ scenarioId, dirty }: { scenarioId: string; dirty: boolean }) {
  const devices = useDevices();
  const run = useRunScenario(scenarioId);
  const [selected, setSelected] = useState<string[]>([]);
  const [msg, setMsg] = useState<string | null>(null);

  function toggle(id: string) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  function start(dry: boolean) {
    setMsg(null);
    run.mutate(
      { target_device_ids: selected, dry_run: dry, confirmed: true },
      {
        onSuccess: (r) => setMsg(`Run ${dry ? "(dry)" : ""} started: ${r.status}`),
        onError: (e) => setMsg((e as Error).message),
      }
    );
  }

  return (
    <div className="p-4">
      <div className="eyebrow mb-2">Run targets</div>
      <div className="mb-3 max-h-44 space-y-1 overflow-y-auto rounded-md border border-[var(--color-hairline)] bg-[var(--color-base)] p-2">
        {(devices.data ?? []).slice(0, 30).map((d) => (
          <label key={d.id} className="flex items-center gap-2 px-1 py-0.5 text-xs text-[var(--color-ink-dim)]">
            <input
              type="checkbox"
              checked={selected.includes(d.id)}
              onChange={() => toggle(d.id)}
              className="accent-[var(--color-active)]"
            />
            {d.name}
          </label>
        ))}
      </div>

      <div className="space-y-2">
        <Button
          variant="primary"
          className="w-full"
          disabled={!scenarioId || selected.length === 0 || dirty || run.isPending}
          onClick={() => start(false)}
        >
          <Play size={14} /> Run scenario
        </Button>
        <Button
          variant="outline"
          className="w-full"
          disabled={!scenarioId || selected.length === 0 || run.isPending}
          onClick={() => start(true)}
        >
          <FlaskConical size={14} /> Dry run
        </Button>
      </div>

      {dirty ? (
        <p className="mt-2 text-[11px] text-[var(--color-warning)]">
          Save as new before running — live runs require an approved version.
        </p>
      ) : (
        <p className="mt-2 text-[11px] text-[var(--color-ink-faint)]">
          Live runs require an approved scenario version and refuse offline devices.
          Dry runs simulate the walk without sending commands.
        </p>
      )}
      {msg ? <p className="mt-2 text-xs text-[var(--color-ink-dim)]">{msg}</p> : null}
    </div>
  );
}

// --- Validation toast -------------------------------------------------------

function ValidationToast({ result, onClose }: { result: ValidationResult; onClose: () => void }) {
  return (
    <div className="absolute bottom-4 left-1/2 z-10 w-[min(560px,90%)] -translate-x-1/2">
      <Panel>
        <PanelHeader
          eyebrow="Validation"
          title={result.valid ? "Scenario is valid" : "Scenario has errors"}
          actions={
            <button onClick={onClose} className="text-[var(--color-ink-faint)] hover:text-[var(--color-ink)]">
              <XCircle size={15} />
            </button>
          }
        />
        <div className="max-h-48 space-y-1 overflow-y-auto p-3 text-xs">
          {result.valid && result.errors.length === 0 ? (
            <div className="flex items-center gap-2 text-[var(--color-online)]">
              <CheckCircle2 size={14} /> All safety checks passed.
            </div>
          ) : null}
          {result.errors.map((e, i) => (
            <div key={`e${i}`} className="flex items-start gap-2 text-[var(--color-alarm)]">
              <XCircle size={13} className="mt-0.5 shrink-0" /> {e}
            </div>
          ))}
          {result.warnings.map((w, i) => (
            <div key={`w${i}`} className="flex items-start gap-2 text-[var(--color-warning)]">
              <span className="mt-1 shrink-0">⚠</span> {w}
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

export default function ScenarioBuilderPage() {
  return (
    <ReactFlowProvider>
      <BuilderInner />
    </ReactFlowProvider>
  );
}
