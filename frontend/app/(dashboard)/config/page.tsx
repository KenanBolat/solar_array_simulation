"use client";
import type { Diagnosis } from "@/lib/types";
import { useState } from "react";
import { api } from "@/lib/api";
import { usePoll } from "@/lib/useApi";
import { usePageHeader } from "@/lib/header-context";
import { useUi } from "@/lib/ui-context";
import { Btn, Panel } from "@/components/ui";

const TABS = [
  "Rack Configuration", "Simulator Units", "Presets",
  "Operational Limits", "Device Groups", "Measurement Retention", "User Permissions",
];
const IMPLEMENTED = ["Rack Configuration", "Simulator Units", "Presets", "Operational Limits"];

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
      {tab === "Presets" && <PresetsTab />}
      {tab === "Operational Limits" && <LimitsConfigTab />}
      {!IMPLEMENTED.includes(tab) && (
        <Panel className="p-10 text-center">
          <div className="mb-1.5 text-[14px] font-semibold">{tab}</div>
          <div className="text-[12px] text-muted">Device groups, retention policy and permission roles configure here.</div>
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
  const [transport, setTransport] = useState("auto");
  const [channels, setChannels] = useState("auto");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [editIp, setEditIp] = useState("");
  const [editMac, setEditMac] = useState("");
  const [editPort, setEditPort] = useState("5025");
  const [editTransport, setEditTransport] = useState("vxi11");
  const [editChannel, setEditChannel] = useState("1");
  const [diag, setDiag] = useState<Record<string, Diagnosis | "running">>({});
  const { data: health } = usePoll(() => api.health(), 30000);

  const diagnose = async (u: any) => {
    setDiag((d) => ({ ...d, [u.name]: "running" }));
    try {
      const r = await api.diagnose(u.name);
      setDiag((d) => ({ ...d, [u.name]: r }));
    } catch (e) {
      notify(e instanceof Error ? e.message : "Diagnosis failed");
      setDiag((d) => { const { [u.name]: _, ...rest } = d; return rest; });
    }
    reload();
  };

  const rackOptions = (racks ?? []).length ? racks!.map((r) => r.id) : ["A"];

  const addInstrument = async () => {
    const trimmed = name.trim();
    if (!trimmed) { notify("Instrument name is required"); return; }
    if (!ip.trim()) { notify("IP address is required"); return; }
    setBusy(true);
    try {
      const r = await api.createInstrument({
        name: trimmed, rack, ipAddress: ip.trim(), macAddress: mac.trim() || undefined,
        scpiPort: port.trim() ? Number(port) : undefined, transport, channels,
      });
      const how = r.detectedChannels ? `instrument reported ${r.detectedChannels} channel(s)` : "configured without asking";
      notify(`Added ${r.created.map((u) => u.label).join(", ")} · ${how}`);
      setName(""); setIp(""); setMac(""); setPort("5025"); setTransport("auto"); setChannels("auto"); setShowForm(false);
      reload();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Failed to add instrument");
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
      ? `${u.ipAddress}${u.transport === "socket" ? ":" + u.scpiPort : ""} · ${u.transport === "socket" ? "socket" : u.transport === "auto" ? "auto (probing)" : "VXI-11"} · (@${u.channel ?? 1})`
      : "no IP set";

  const resetAll = async () => {
    try {
      const r = await api.resetConnections();
      const online = r.units.filter((x) => x.online).length;
      notify(`Dropped ${r.dropped} session${r.dropped === 1 ? "" : "s"} · re-polled ${r.units.length} units · ${online} online`);
    } catch (e) {
      notify(e instanceof Error ? e.message : "Reset failed");
    }
    reload();
  };

  const discoverChannels = async () => {
    try {
      const r = await api.discoverChannels();
      const found = r.mainframes.map((m) => `${m.mainframe}: ${m.channels ?? "?"} ch${m.error ? ` (${m.error})` : ""}`).join(" · ");
      notify(r.created.length ? `Added ${r.created.join(", ")} · ${found}` : `No new channels · ${found}`);
    } catch (e) {
      notify(e instanceof Error ? e.message : "Discovery failed");
    }
    reload();
  };

  const applyFleet = () => {
    ask({
      title: "Apply fleet file",
      message: `Re-reads the backend's fleet file and re-addresses the stored units to match it (adding any that are missing). Measurements, command history and alarms are kept. Use this when the units here still point somewhere else — e.g. at the local emulators — after the fleet file changed.`,
      confirmLabel: "Apply fleet file", danger: false,
      onConfirm: async () => {
        try {
          const r = await api.applyFleet();
          const parts = [
            r.readdressed.length ? `re-addressed ${r.readdressed.join(", ")}` : "",
            r.added.length ? `added ${r.added.join(", ")}` : "",
            r.unchanged.length ? `${r.unchanged.length} already matching` : "",
          ].filter(Boolean);
          notify(parts.length ? parts.join(" · ") : "Nothing to change");
        } catch (e) {
          notify(e instanceof Error ? e.message : "Apply failed");
        }
        reload();
      },
    });
  };

  const rebootUnit = (u: any) => {
    ask({
      title: `Reboot mainframe — ${u.name}`,
      message: `Sends SYST:REBoot to ${u.ipAddress}. The mainframe restarts (~30 s), its output goes OFF, and every session on it is dropped — including telnet or VISA sessions held on other machines. This is the only way to free a session the app doesn't own. If a second unit is configured on the same IP (channel 2), it reboots too.`,
      confirmLabel: "Send SYST:REB", danger: true,
      onConfirm: async () => {
        try { await api.rebootUnit(u.name); notify(`${u.name} · SYST:REB sent — allow ~30 s`); }
        catch (e) { notify(e instanceof Error ? e.message : "Reboot failed"); }
        reload();
      },
    });
  };

  return (
    <Panel className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div>
          <div className="text-[13px] font-semibold">Simulator Units</div>
          {health && (
            <div className="mt-0.5 font-mono text-[10px] text-faint">
              backend on <span className="text-[#cfd6e2]">{health.host.hostname}</span>
              {health.host.ips.length > 0 && (
                <> · LAN users open <span className="text-cyan">http://{health.host.ips[0]}:{health.uiPort}</span></>
              )}
              {health.emulatedUnits > 0 && (
                <span className="text-amber"> · {health.emulatedUnits} unit(s) point at the local emulators, not real instruments — use “Apply fleet file”</span>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span title="Ask each mainframe how many output channels it has (SYST:CHAN?) and add any that aren't configured"><Btn onClick={discoverChannels}>Discover channels</Btn></span>
          <span title="Re-address the stored units from the backend's fleet file"><Btn onClick={applyFleet}>Apply fleet file</Btn></span>
          <span title="Close every instrument session this app holds and re-poll all units now"><Btn onClick={resetAll}>⟲ Reset all connections</Btn></span>
          <Btn variant="primary" onClick={() => setShowForm((s) => !s)}>{showForm ? "Cancel" : "+ Add Instrument"}</Btn>
        </div>
      </div>
      <div className="grid gap-2.5 border-b border-line px-4 py-2 font-mono text-[9.5px] uppercase tracking-wider text-faint" style={{ gridTemplateColumns: "80px 70px 40px 1fr 60px 130px 230px" }}>
        <span>Unit</span><span>Rack</span><span>Slot</span><span>Address (IP · transport · channel / MAC)</span><span>Poll</span><span>State</span><span>Actions</span>
      </div>
      {(units ?? []).map((u: any) => (
        <div key={u.name} className="border-b border-[#161b24]">
        <div className="grid items-center gap-2.5 px-4 py-2.5 font-mono text-[11px]" style={{ gridTemplateColumns: "80px 70px 40px 1fr 60px 130px 230px" }}>
          <span className="font-bold" title={u.name}>{u.label ?? u.name}</span>
          <span className="text-[#cfd6e2]">{u.rack}</span>
          <span className="text-muted">{u.slot}</span>
          {editing === u.name ? (
            <span className="flex items-center gap-1.5">
              <input value={editIp} onChange={(e) => setEditIp(e.target.value)} placeholder="IP address"
                className="w-[110px] rounded border border-line2 bg-bg px-1.5 py-1 font-mono text-[10.5px] text-ink" />
              <select value={editTransport} onChange={(e) => setEditTransport(e.target.value)}
                className="rounded border border-line2 bg-bg px-1 py-1 font-mono text-[10.5px] text-ink">
                <option value="auto">auto</option>
                <option value="vxi11">VXI-11</option>
                <option value="socket">socket</option>
              </select>
              {editTransport !== "vxi11" && (
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
              <span className="text-[9.5px] font-semibold" style={{ color: u.online ? "#34d399" : "#f87171" }} title={u.lastError ?? ""}>
                {u.online ? "● reachable" : "● unreachable"}
              </span>
            )}
            {u.enabled && !u.online && u.lastError && (
              <span className="whitespace-normal break-words text-[9px] leading-snug text-[#f8717199]">{u.lastError}</span>
            )}
          </span>
          <span className="flex flex-wrap gap-1.5">
            {u.enabled && !u.online && (
              <button onClick={async () => { const r = await api.reconnect(u.name); notify(`${u.name} · ${r.result}`); reload(); }}
                className="rounded border border-cyan/50 bg-cyan/10 px-2 py-1 font-sans text-[10px] font-semibold text-cyan" title="Drop the cached connection and poll now">
                Reconnect
              </button>
            )}
            <button onClick={() => toggleEnabled(u)} className="rounded border border-line2 bg-panel2 px-2 py-1 font-sans text-[10px] font-semibold text-ink">
              {u.enabled ? "Disable" : "Enable"}
            </button>
            <button onClick={() => diagnose(u)} disabled={diag[u.name] === "running"} title="Probe this address from the backend host: ports, VXI-11 and socket *IDN?"
              className="rounded border border-line2 bg-panel2 px-2 py-1 font-sans text-[10px] font-semibold text-ink disabled:opacity-50">
              {diag[u.name] === "running" ? "Probing…" : "Diagnose"}
            </button>
            {u.enabled && u.transport !== "auto" && (
              <button onClick={() => rebootUnit(u)} title="SYST:REBoot — drops every session on the mainframe, output OFF, ~30 s"
                className="rounded border border-amber/40 bg-amber/10 px-2 py-1 font-sans text-[10px] font-semibold text-amber">
                Reboot
              </button>
            )}
            <button onClick={() => deleteUnit(u)} className="rounded border border-red/40 bg-red/10 px-2 py-1 font-sans text-[10px] font-semibold text-red">
              Delete
            </button>
          </span>
        </div>
        {diag[u.name] && diag[u.name] !== "running" && (() => {
          const d = diag[u.name] as Diagnosis;
          return (
            <div className="mx-4 mb-3 rounded-md border border-line2 bg-bg px-3 py-2.5 font-mono text-[10.5px]">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="text-faint">probe of <span className="text-[#cfd6e2]">{d.ip}</span> from <span className="text-[#cfd6e2]">{d.from.hostname}</span> ({d.from.ips.join(", ") || "no LAN IP"})</span>
                <button onClick={() => setDiag((x) => { const { [u.name]: _, ...rest } = x; return rest; })} className="text-faint hover:text-ink">✕</button>
              </div>
              {d.checks.map((c) => (
                <div key={c.check} className="grid gap-2 py-0.5" style={{ gridTemplateColumns: "190px 1fr" }}>
                  <span style={{ color: c.ok ? "#34d399" : "#f87171" }}>{c.ok ? "● " : "○ "}{c.check}</span>
                  <span className="break-all text-[#cfd6e2]">{c.detail}</span>
                </div>
              ))}
              <div className="mt-1.5 border-t border-line pt-1.5 font-sans text-[11px]" style={{ color: d.recommend ? "#34d399" : "#fbbf24" }}>{d.verdict}</div>
            </div>
          );
        })()}
        </div>
      ))}
      {(units ?? []).length === 0 && (
        <div className="px-4 py-6 text-center text-[12px] text-faint">No simulator units configured yet.</div>
      )}

      {showForm && (
        <div className="border-t border-line px-4 py-3.5">
          <div className="mb-2.5 text-[11px] text-muted">New instrument — one E4360 mainframe and a unit for each of its output channels</div>
          <div className="grid grid-cols-8 gap-2.5">
            <div>
              <label className="mb-1 block text-[10px] text-faint">Instrument Name</label>
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
                <option value="auto">auto (VXI-11, then socket)</option>
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
              <label className="mb-1 block text-[10px] text-faint">Channels</label>
              <select value={channels} onChange={(e) => setChannels(e.target.value)}
                className="w-full rounded-md border border-line2 bg-bg px-2.5 py-2 text-[12px] text-ink">
                <option value="auto">Auto-detect</option>
                <option value="1">Channel 1 only</option>
                <option value="2">Both channels</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-[10px] text-faint">MAC Address</label>
              <input value={mac} onChange={(e) => setMac(e.target.value)} placeholder="xx-xx-xx-xx-xx-xx"
                className="w-full rounded-md border border-line2 bg-bg px-2.5 py-2 font-mono text-[12px] text-ink" />
            </div>
            <div className="flex items-end">
              <Btn variant="primary" className="w-full" disabled={busy} onClick={addInstrument}>Add Instrument</Btn>
            </div>
          </div>
          <div className="mt-2 text-[10px] leading-relaxed text-faint">
            One unit is created per output channel, shown as <span className="font-mono">{name.trim() || "SAS-03"} (@1)</span>, <span className="font-mono">{name.trim() || "SAS-03"} (@2)</span>.
            <b className="text-[#cfd6e2]"> Auto-detect</b> asks the instrument itself (<span className="font-mono">SYST:CHAN?</span>) rather than assuming — if it can&apos;t be reached, only channel 1 is configured and <b className="text-[#cfd6e2]">Discover channels</b> can add the rest later.
            <b className="text-[#cfd6e2]"> auto</b> tries VXI-11 first, then the raw socket on the port given, and pins whichever answers.
            <b className="text-[#cfd6e2]"> VXI-11</b> is the LAN interface the E4360 Programmer&apos;s Reference documents (<span className="font-mono">TCPIP0::&lt;ip&gt;::INSTR</span>).
            <b className="text-[#cfd6e2]"> Raw socket</b> sends the same SCPI over a plain TCP port — only pick it if your instrument&apos;s LAN page confirms the port; it&apos;s what the bundled emulators on 127.0.0.1 use.
            The MAC is a label only. Every second the unit is asked <span className="font-mono">MEAS:VOLT?</span> / <span className="font-mono">FETC:CURR?</span> / <span className="font-mono">OUTP?</span> / <span className="font-mono">CURR:MODE?</span> / <span className="font-mono">STAT:QUES:COND?</span>; no valid reply means unreachable and a null sample.
          </div>
        </div>
      )}
    </Panel>
  );
}

const BLANK_PRESET = { name: "", mode: "FIX" as "FIX" | "SAS", volt: "28.0", curr: "5.0", isc: "4.6", imp: "4.2", vmp: "28.0", voc: "32.0", note: "" };

function PresetsTab() {
  const { notify, ask } = useUi();
  const { data, reload } = usePoll(() => api.presets(), 10000);
  const { data: units } = usePoll(() => api.units(), 10000);
  const [form, setForm] = useState(BLANK_PRESET);
  const [showForm, setShowForm] = useState(false);
  const [target, setTarget] = useState<string>("");

  const presets = data?.presets ?? [];
  const max = data?.max ?? 10;
  const full = presets.length >= max;
  const targets = (units ?? []).filter((u) => u.enabled);
  const chosen = target || targets[0]?.name || "";

  const insert = async () => {
    const num = (k: keyof typeof BLANK_PRESET) => parseFloat(form[k] as string) || 0;
    try {
      await api.createPreset({
        name: form.name, mode: form.mode, note: form.note,
        volt: num("volt"), curr: num("curr"), isc: num("isc"), imp: num("imp"), vmp: num("vmp"), voc: num("voc"),
      });
      notify(`Preset “${form.name}” inserted`);
      setForm(BLANK_PRESET); setShowForm(false); reload();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Insert failed");
    }
  };

  const remove = (p: any) => {
    ask({
      title: `Delete preset — ${p.name}`,
      message: "Removes this stored operating point. Nothing on the instrument changes.",
      confirmLabel: "Delete preset", danger: true,
      onConfirm: async () => { await api.deletePreset(p.id); notify(`Deleted “${p.name}”`); reload(); },
    });
  };

  const apply = (p: any) => {
    if (!chosen) { notify("No unit available to apply to"); return; }
    const detail = p.mode === "SAS"
      ? `Isc ${p.isc} A · Imp ${p.imp} A · Vmp ${p.vmp} V · Voc ${p.voc} V`
      : `${p.volt} V · ${p.curr} A`;
    const current = (units ?? []).find((u) => u.name === chosen);
    const switching = current?.opMode && current.opMode !== p.mode;
    ask({
      title: `Apply “${p.name}” to ${chosen}`,
      message: `A preset is a complete operating point: this sends CURR:MODE ${p.mode} first, then ${detail}.`
        + (switching ? `\n\n⚠ ${chosen} is in ${current!.opMode} mode — this SWITCHES it to ${p.mode}.` : "")
        + `\n\nEvery command is confirmed by readback and recorded in the audit log.`,
      confirmLabel: "Apply preset", danger: false,
      onConfirm: async () => {
        try { await api.applyPreset(p.id, chosen); notify(`“${p.name}” applied to ${chosen}`); }
        catch (e) { notify(e instanceof Error ? e.message : "Apply failed"); }
      },
    });
  };

  const GRID = "34px 1fr 54px 1.5fr 70px 190px";

  return (
    <Panel className="overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div>
          <div className="text-[13px] font-semibold">Presets</div>
          <div className="mt-0.5 font-mono text-[10px] text-faint">
            {presets.length} of {max} · applying one sends <span className="text-[#cfd6e2]">CURR:MODE</span> first, so a preset also switches FIX ↔ SAS · the instrument&apos;s own <span className="text-[#cfd6e2]">*SAV/*RCL</span> slots (0 and 1) live in the Virtual Front Panel
          </div>
        </div>
        <div className="flex items-center gap-2">
          {targets.length > 0 && (
            <select value={chosen} onChange={(e) => setTarget(e.target.value)} title="Unit that Apply sends to"
              className="rounded-md border border-line2 bg-bg px-2 py-1.5 font-mono text-[11px] text-ink">
              {targets.map((u) => <option key={u.name} value={u.name}>{u.label}</option>)}
            </select>
          )}
          <Btn variant="primary" disabled={full && !showForm} onClick={() => setShowForm((s) => !s)}>
            {showForm ? "Cancel" : full ? `Full (${max})` : "+ Insert preset"}
          </Btn>
        </div>
      </div>

      <div className="grid gap-2.5 border-b border-line px-4 py-2 font-mono text-[9.5px] uppercase tracking-wider text-faint" style={{ gridTemplateColumns: GRID }}>
        <span>On</span><span>Name</span><span>Mode</span><span>Values</span><span>Pmp</span><span>Actions</span>
      </div>
      {presets.map((p) => (
        <div key={p.id} className="grid items-center gap-2.5 border-b border-[#161b24] px-4 py-2.5 font-mono text-[11px]" style={{ gridTemplateColumns: GRID }}>
          <input type="checkbox" checked={p.enabled} title={p.enabled ? "Enabled — can be applied" : "Disabled"}
            onChange={async () => { await api.enablePreset(p.id, !p.enabled); reload(); }}
            className="h-3.5 w-3.5 accent-cyan" />
          <span className="flex min-w-0 flex-col">
            <span className="truncate font-sans font-semibold" style={{ color: p.enabled ? "#e6eaf2" : "#5c6678" }}>{p.name}</span>
            {p.note && <span className="truncate text-[9.5px] text-faint">{p.note}</span>}
          </span>
          <span className="rounded px-1.5 py-0.5 text-center text-[10px] font-bold"
            style={{ color: p.mode === "SAS" ? "#fbbf24" : "#2dd4ee", border: `1px solid ${p.mode === "SAS" ? "#fbbf2455" : "#2dd4ee55"}` }}>{p.mode}</span>
          <span className="truncate text-[#cfd6e2]">
            {p.mode === "SAS"
              ? `Isc ${p.isc} A · Imp ${p.imp} A · Vmp ${p.vmp} V · Voc ${p.voc} V`
              : `${p.volt} V · ${p.curr} A`}
          </span>
          <span className="text-muted">{p.mode === "SAS" ? `${(p.vmp * p.imp).toFixed(1)} W` : `${(p.volt * p.curr).toFixed(1)} W`}</span>
          <span className="flex gap-1.5">
            <button onClick={() => apply(p)} disabled={!p.enabled || !chosen}
              className="rounded border border-cyan/50 bg-cyan/10 px-2 py-1 font-sans text-[10px] font-semibold text-cyan disabled:opacity-40">
              Apply{chosen ? ` → ${chosen}` : ""}
            </button>
            <button onClick={() => remove(p)} className="rounded border border-red/40 bg-red/10 px-2 py-1 font-sans text-[10px] font-semibold text-red">Delete</button>
          </span>
        </div>
      ))}
      {presets.length === 0 && <div className="px-4 py-6 text-center text-[12px] text-faint">No presets stored yet.</div>}

      {showForm && (
        <div className="border-t border-line px-4 py-3.5">
          <div className="mb-2.5 text-[11px] text-muted">New preset</div>
          <div className="mb-2.5 flex gap-2.5">
            <div className="w-[220px]">
              <label className="mb-1 block text-[10px] text-faint">Name</label>
              <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Eclipse exit"
                className="w-full rounded-md border border-line2 bg-bg px-2.5 py-2 font-mono text-[12px] text-ink" />
            </div>
            <div className="w-[120px]">
              <label className="mb-1 block text-[10px] text-faint">Mode</label>
              <select value={form.mode} onChange={(e) => setForm((f) => ({ ...f, mode: e.target.value as "FIX" | "SAS" }))}
                className="w-full rounded-md border border-line2 bg-bg px-2.5 py-2 text-[12px] text-ink">
                <option value="FIX">FIX</option>
                <option value="SAS">SAS</option>
              </select>
            </div>
            <div className="flex-1">
              <label className="mb-1 block text-[10px] text-faint">Note (optional)</label>
              <input value={form.note} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} placeholder="what this operating point is for"
                className="w-full rounded-md border border-line2 bg-bg px-2.5 py-2 text-[12px] text-ink" />
            </div>
          </div>
          <div className="mb-2.5 grid grid-cols-4 gap-2.5">
            {(form.mode === "SAS"
              ? ([["isc", "Isc — short circuit (A)"], ["imp", "Imp — at peak power (A)"], ["vmp", "Vmp — at peak power (V)"], ["voc", "Voc — open circuit (V)"]] as const)
              : ([["volt", "Voltage (V)"], ["curr", "Current limit (A)"]] as const)
            ).map(([k, label]) => (
              <div key={k}>
                <label className="mb-1 block text-[10px] text-faint">{label}</label>
                <input value={form[k] as string} onChange={(e) => setForm((f) => ({ ...f, [k]: e.target.value }))}
                  className="w-full rounded-md border border-line2 bg-bg px-2.5 py-2 font-mono text-[12px] text-ink" />
              </div>
            ))}
          </div>
          <Btn variant="primary" onClick={insert}>Insert preset</Btn>
          <div className="mt-2 text-[10px] leading-relaxed text-faint">
            {form.mode === "SAS"
              ? "The four curve parameters are coupled — the instrument validates them together and rejects the set if Vmp ≥ Voc (320), Imp > Isc (321) or the peak point is too small (322)."
              : "FIX mode programs a rectangular characteristic; the instrument rejects VOLT/CURR while a channel is in SAS mode (315)."}
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
