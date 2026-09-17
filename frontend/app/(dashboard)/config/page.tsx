"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { usePageHeader } from "@/lib/header-context";
import { useUi } from "@/lib/ui-context";
import { Btn, Panel } from "@/components/ui";

const TABS = [
  "Rack Configuration", "Simulator Units", "Connection Profiles",
  "Operational Limits", "Device Groups", "Measurement Retention", "User Permissions",
];

export default function ConfigPage() {
  usePageHeader("Configuration", "Administrator · system setup");
  const [tab, setTab] = useState(TABS[0]);

  return (
    <div className="p-5">
      <div className="mb-4.5 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <div key={t} onClick={() => setTab(t)}
            className="cursor-pointer whitespace-nowrap rounded-md px-3.5 py-2 text-[12px] font-semibold"
            style={{
              color: t === tab ? "#fff" : "#8a95a8",
              background: t === tab ? "#2dd4ee1f" : "transparent",
              border: `1px solid ${t === tab ? "#2dd4ee55" : "transparent"}`,
            }}>
            {t}
          </div>
        ))}
      </div>

      {tab === "Rack Configuration" && <RackConfigTab />}
      {tab === "Simulator Units" && <UnitsConfigTab />}
      {tab === "Operational Limits" && <LimitsConfigTab />}
      {!["Rack Configuration", "Simulator Units", "Operational Limits"].includes(tab) && (
        <Panel className="p-10 text-center">
          <div className="mb-1.5 text-[14px] font-semibold">{tab}</div>
          <div className="text-[12px] text-muted">Connection profiles, device groups, retention policy and permission roles configure here.</div>
        </Panel>
      )}
    </div>
  );
}

function RackConfigTab() {
  const { data: racks } = usePoll(() => api.configRacks(), 8000);
  const rack = (racks ?? [])[0];
  const rackId = rack?.id ?? "A";
  const { data: editor, reload } = usePoll(() => api.rackEditor(rackId), 4000, [rackId]);
  const [dragging, setDragging] = useState<string | null>(null);

  const onDrop = async (slot: string) => {
    if (!dragging) return;
    await api.assignUnit(slot, dragging);
    setDragging(null);
    reload();
  };

  return (
    <div className="grid grid-cols-[1fr_380px] items-start gap-4.5">
      <Panel className="p-4">
        <div className="mb-3.5 flex items-center justify-between">
          <div className="text-[13px] font-semibold">Rack Configuration</div>
          <Btn variant="primary">+ Add Rack</Btn>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Rack Name" value={rack?.name ?? "—"} />
          <Field label="Location" value={rack?.loc ?? ""} />
          <Field label="Capacity (slots)" value={String(rack?.cap ?? "—")} mono />
          <Field label="Units Assigned" value={String(rack?.unitsAssigned ?? 0)} mono />
        </div>
        <div className="mt-3.5 text-[11px] text-muted">Drag unassigned units from the palette into rack slots →</div>
      </Panel>

      <Panel className="p-3.5">
        <div className="mb-2.5 text-[12px] font-semibold">Rack Position Editor · {rack?.name ?? "—"}</div>
        <div className="mb-3.5 flex flex-col gap-1.5">
          {(editor?.slots ?? []).map((s) => (
            <div key={s.key}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => onDrop(s.key)}
              className="flex min-h-[42px] items-center gap-2 rounded-md px-3 py-2"
              style={{
                border: s.occ ? "1.5px solid #2c3543" : "1.5px dashed #2c3543",
                background: s.occ ? "#1a1f29" : "#ffffff05",
              }}>
              <span className="w-[46px] flex-none font-mono text-[10px] text-faint">{s.label}</span>
              {s.empty ? (
                <span className="text-[11px] italic text-faint">drop unit here</span>
              ) : (
                <span className="font-mono text-[12px] font-bold text-cyan">{s.occ}</span>
              )}
            </div>
          ))}
          {(editor?.slots ?? []).length === 0 && <div className="text-[11px] text-faint">No rack found.</div>}
        </div>
        <div className="mb-2 text-[10px] uppercase tracking-wider text-faint">Unassigned Units</div>
        <div className="flex flex-wrap gap-2">
          {(editor?.palette ?? []).map((name) => (
            <div key={name} draggable onDragStart={() => setDragging(name)}
              className="flex cursor-grab items-center gap-2 rounded-md border border-cyan/40 bg-cyan/[0.08] px-2.5 py-2 text-[12px] font-semibold text-cyan">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan" />{name}
            </div>
          ))}
          {(editor?.palette ?? []).length === 0 && <div className="text-[11px] text-faint">No units from other racks to assign here.</div>}
        </div>
      </Panel>
    </div>
  );
}

function UnitsConfigTab() {
  const { notify, ask } = useUi();
  const { data: units, reload } = usePoll(() => api.configUnits(), 5000);
  const { data: racks } = usePoll(() => api.configRacks(), 8000);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [rack, setRack] = useState("A");
  const [ip, setIp] = useState("");
  const [mac, setMac] = useState("");
  const [port, setPort] = useState("5025");
  const [transport, setTransport] = useState("vxi11");
  const [channel, setChannel] = useState("1");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [editIp, setEditIp] = useState("");
  const [editMac, setEditMac] = useState("");
  const [editPort, setEditPort] = useState("5025");
  const [editTransport, setEditTransport] = useState("vxi11");
  const [editChannel, setEditChannel] = useState("1");

  const rackOptions = (racks ?? []).length ? racks!.map((r) => r.id) : ["A"];

  const addUnit = async () => {
    const trimmed = name.trim();
    if (!trimmed) { notify("Unit name is required"); return; }
    setBusy(true);
    try {
      await api.createUnit({
        name: trimmed, rack, ipAddress: ip.trim() || undefined, macAddress: mac.trim() || undefined,
        scpiPort: port.trim() ? Number(port) : undefined, transport, channel: Number(channel),
      });
      notify(`Added ${trimmed}`);
      setName(""); setIp(""); setMac(""); setPort("5025"); setTransport("vxi11"); setChannel("1"); setShowForm(false);
      reload();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Failed to add unit");
    } finally {
      setBusy(false);
    }
  };

  const toggleEnabled = async (u: any) => {
    if (u.enabled) await api.disableUnit(u.name);
    else await api.enableUnit(u.name);
    notify(`${u.name} ${u.enabled ? "disabled" : "enabled"}`);
    reload();
  };

  const deleteUnit = (u: any) => {
    ask({
      title: `Delete ${u.name}`,
      message: `This permanently removes ${u.name} from the fleet and frees its rack slot. Its command-history and alarm records are kept for traceability, but its measurement history is deleted.`,
      confirmLabel: "Delete unit", danger: true,
      onConfirm: async () => {
        await api.deleteUnit(u.name);
        notify(`Deleted ${u.name}`);
        reload();
      },
    });
  };

  const startEdit = (u: any) => {
    setEditing(u.name); setEditIp(u.ipAddress); setEditMac(u.macAddress); setEditPort(String(u.scpiPort));
    setEditTransport(u.transport ?? "vxi11"); setEditChannel(String(u.channel ?? 1));
  };
  const saveEdit = async (name: string) => {
    try {
      await api.updateNetwork(name, {
        ipAddress: editIp.trim(), macAddress: editMac.trim(), scpiPort: editPort.trim() ? Number(editPort) : undefined,
        transport: editTransport, channel: Number(editChannel),
      });
      notify(`Updated addressing · ${name} — re-polling`);
      setEditing(null);
      reload();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Failed to update");
    }
  };

  const describeAddress = (u: any) =>
    u.ipAddress
      ? `${u.ipAddress}${u.transport === "socket" ? ":" + u.scpiPort : ""} · ${u.transport === "socket" ? "socket" : "VXI-11"} · (@${u.channel ?? 1})`
      : "no IP set";

  return (
    <Panel className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="text-[13px] font-semibold">Simulator Units</div>
        <Btn variant="primary" onClick={() => setShowForm((s) => !s)}>{showForm ? "Cancel" : "+ Add Simulator Unit"}</Btn>
      </div>
      <div className="grid gap-2.5 border-b border-line px-4 py-2 font-mono text-[9.5px] uppercase tracking-wider text-faint" style={{ gridTemplateColumns: "80px 70px 40px 1fr 60px 130px 160px" }}>
        <span>Unit</span><span>Rack</span><span>Slot</span><span>Address (IP · transport · channel / MAC)</span><span>Poll</span><span>State</span><span>Actions</span>
      </div>
      {(units ?? []).map((u: any) => (
        <div key={u.name} className="grid items-center gap-2.5 border-b border-[#161b24] px-4 py-2.5 font-mono text-[11px]" style={{ gridTemplateColumns: "80px 70px 40px 1fr 60px 130px 160px" }}>
          <span className="font-bold">{u.name}</span>
          <span className="text-[#cfd6e2]">{u.rack}</span>
          <span className="text-muted">{u.slot}</span>
          {editing === u.name ? (
            <span className="flex items-center gap-1.5">
              <input value={editIp} onChange={(e) => setEditIp(e.target.value)} placeholder="IP address"
                className="w-[110px] rounded border border-line2 bg-bg px-1.5 py-1 font-mono text-[10.5px] text-ink" />
              <select value={editTransport} onChange={(e) => setEditTransport(e.target.value)}
                className="rounded border border-line2 bg-bg px-1 py-1 font-mono text-[10.5px] text-ink">
                <option value="vxi11">VXI-11</option>
                <option value="socket">socket</option>
              </select>
              {editTransport === "socket" && (
                <input value={editPort} onChange={(e) => setEditPort(e.target.value)} placeholder="port"
                  className="w-[52px] rounded border border-line2 bg-bg px-1.5 py-1 font-mono text-[10.5px] text-ink" />
              )}
              <select value={editChannel} onChange={(e) => setEditChannel(e.target.value)} title="output channel (@n)"
                className="rounded border border-line2 bg-bg px-1 py-1 font-mono text-[10.5px] text-ink">
                <option value="1">(@1)</option>
                <option value="2">(@2)</option>
              </select>
              <input value={editMac} onChange={(e) => setEditMac(e.target.value)} placeholder="MAC address"
                className="w-[120px] rounded border border-line2 bg-bg px-1.5 py-1 font-mono text-[10.5px] text-ink" />
              <button onClick={() => saveEdit(u.name)} className="rounded border border-cyan/50 bg-cyan/10 px-2 py-1 font-sans text-[10px] font-semibold text-cyan">Save</button>
              <button onClick={() => setEditing(null)} className="rounded border border-line2 bg-panel2 px-2 py-1 font-sans text-[10px] font-semibold text-ink">Cancel</button>
            </span>
          ) : (
            <span className="flex min-w-0 flex-col cursor-pointer" onClick={() => startEdit(u)} title="Click to edit — the instrument is queried over SCPI at this address every second">
              <span className="truncate text-[10.5px] text-[#cfd6e2]">{describeAddress(u)}</span>
              <span className="truncate text-[9.5px] text-faint">{u.macAddress || "no MAC set"}{u.opMode ? ` · mode ${u.opMode}` : ""}</span>
            </span>
          )}
          <span className="text-muted">{u.poll}</span>
          <span className="flex flex-col gap-0.5">
            <span className="font-semibold" style={{ color: u.enabled ? "#34d399" : "#5c6678" }}>{u.enabled ? "Enabled" : "Disabled"}</span>
            {u.enabled && (
              <span className="text-[9.5px] font-semibold" style={{ color: u.online ? "#34d399" : "#f87171" }}>
                {u.online ? "● reachable" : "● unreachable"}
              </span>
            )}
          </span>
          <span className="flex flex-wrap gap-1.5">
            <button onClick={() => toggleEnabled(u)} className="rounded border border-line2 bg-panel2 px-2 py-1 font-sans text-[10px] font-semibold text-ink">
              {u.enabled ? "Disable" : "Enable"}
            </button>
            <button onClick={() => deleteUnit(u)} className="rounded border border-red/40 bg-red/10 px-2 py-1 font-sans text-[10px] font-semibold text-red">
              Delete
            </button>
          </span>
        </div>
      ))}
      {(units ?? []).length === 0 && (
        <div className="px-4 py-6 text-center text-[12px] text-faint">No simulator units configured yet.</div>
      )}

      {showForm && (
        <div className="border-t border-line px-4 py-3.5">
          <div className="mb-2.5 text-[11px] text-muted">New unit</div>
          <div className="grid grid-cols-8 gap-2.5">
            <div>
              <label className="mb-1 block text-[10px] text-faint">Unit Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="SAS-03"
                className="w-full rounded-md border border-line2 bg-bg px-2.5 py-2 font-mono text-[12px] text-ink" />
            </div>
            <div>
              <label className="mb-1 block text-[10px] text-faint">Rack</label>
              <select value={rack} onChange={(e) => setRack(e.target.value)}
                className="w-full rounded-md border border-line2 bg-bg px-2.5 py-2 text-[12px] text-ink">
                {rackOptions.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-[10px] text-faint">IP Address</label>
              <input value={ip} onChange={(e) => setIp(e.target.value)} placeholder="10.1.20.x"
                className="w-full rounded-md border border-line2 bg-bg px-2.5 py-2 font-mono text-[12px] text-ink" />
            </div>
            <div>
              <label className="mb-1 block text-[10px] text-faint">Transport</label>
              <select value={transport} onChange={(e) => setTransport(e.target.value)}
                className="w-full rounded-md border border-line2 bg-bg px-2.5 py-2 text-[12px] text-ink">
                <option value="vxi11">VXI-11 (documented)</option>
                <option value="socket">Raw socket</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-[10px] text-faint">Port {transport === "vxi11" && <span className="text-faint/60">(socket only)</span>}</label>
              <input value={port} onChange={(e) => setPort(e.target.value)} placeholder="5025" disabled={transport === "vxi11"}
                className="w-full rounded-md border border-line2 bg-bg px-2.5 py-2 font-mono text-[12px] text-ink disabled:opacity-40" />
            </div>
            <div>
              <label className="mb-1 block text-[10px] text-faint">Channel</label>
              <select value={channel} onChange={(e) => setChannel(e.target.value)}
                className="w-full rounded-md border border-line2 bg-bg px-2.5 py-2 font-mono text-[12px] text-ink">
                <option value="1">(@1)</option>
                <option value="2">(@2)</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-[10px] text-faint">MAC Address</label>
              <input value={mac} onChange={(e) => setMac(e.target.value)} placeholder="xx-xx-xx-xx-xx-xx"
                className="w-full rounded-md border border-line2 bg-bg px-2.5 py-2 font-mono text-[12px] text-ink" />
            </div>
            <div className="flex items-end">
              <Btn variant="primary" className="w-full" disabled={busy} onClick={addUnit}>Create Unit</Btn>
            </div>
          </div>
          <div className="mt-2 text-[10px] leading-relaxed text-faint">
            A unit is one output channel <span className="font-mono">(@1)</span> or <span className="font-mono">(@2)</span> of one E4360 mainframe at this IP.
            <b className="text-[#cfd6e2]"> VXI-11</b> is the LAN interface the E4360 Programmer&apos;s Reference documents (<span className="font-mono">TCPIP0::&lt;ip&gt;::INSTR</span>).
            <b className="text-[#cfd6e2]"> Raw socket</b> sends the same SCPI over a plain TCP port — only pick it if your instrument&apos;s LAN page confirms the port; it&apos;s what the bundled emulators on 127.0.0.1 use.
            The MAC is a label only. Every second the unit is asked <span className="font-mono">MEAS:VOLT?</span> / <span className="font-mono">FETC:CURR?</span> / <span className="font-mono">OUTP?</span> / <span className="font-mono">CURR:MODE?</span> / <span className="font-mono">STAT:QUES:COND?</span>; no valid reply means unreachable and a null sample.
          </div>
        </div>
      )}
    </Panel>
  );
}

function LimitsConfigTab() {
  const { data: limits } = usePoll(() => api.configLimits(), 8000);
  if (!limits) return null;
  return (
    <div className="grid grid-cols-2 items-start gap-4.5">
      <Panel className="p-4">
        <div className="mb-3.5 text-[13px] font-semibold">Operational Limits</div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Maximum Voltage (V)" value={limits.max_voltage_v.toFixed(1)} mono />
          <Field label="Maximum Current (A)" value={limits.max_current_a.toFixed(1)} mono />
          <Field label="Maximum Power (W)" value={limits.max_power_w.toFixed(1)} mono />
          <SelectField label="Allowed Output State" options={[limits.allowed_output_state, "OFF only (locked)"]} />
        </div>
      </Panel>
      <Panel className="p-4">
        <div className="mb-3.5 text-[13px] font-semibold">Alarm Thresholds &amp; Safe Shutdown</div>
        <div className="flex flex-col gap-2.5">
          <ThresholdRow label="Warning threshold · power" value={`${limits.warning_threshold_power_w} W`} color="#fbbf24" />
          <ThresholdRow label="Critical threshold · power" value={`${limits.critical_threshold_power_w} W`} color="#f87171" />
          <div className="flex items-center justify-between rounded-md border border-line2 bg-bg px-2.5 py-2.5">
            <span className="text-[12px] text-[#cfd6e2]">Safe shutdown rule</span>
            <span className="font-mono text-[12px] text-ink">{limits.safe_shutdown_rule}</span>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function ThresholdRow({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="flex items-center justify-between rounded-md px-2.5 py-2.5" style={{ background: `${color}0d`, border: `1px solid ${color}33` }}>
      <span className="text-[12px] text-[#cfd6e2]">{label}</span>
      <span className="font-mono text-[13px]" style={{ color }}>{value}</span>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <label className="mb-1 block text-[10px] text-faint">{label}</label>
      <input readOnly value={value} className={`w-full rounded-md border border-line2 bg-bg px-2.5 py-2 text-[13px] text-ink ${mono ? "font-mono" : ""}`} />
    </div>
  );
}

function SelectField({ label, options }: { label: string; options: string[] }) {
  return (
    <div>
      <label className="mb-1 block text-[10px] text-faint">{label}</label>
      <select className="w-full rounded-md border border-line2 bg-bg px-2.5 py-2 text-[12px] text-ink">
        {options.map((o) => <option key={o}>{o}</option>)}
      </select>
    </div>
  );
}
