"""Seed data for the Solar Array Simulator Control Platform.

Creates a realistic on-premise lab configuration entirely in SIMULATION MODE:

  * RBAC: 5 permissions, 4 roles, one demo user per role
  * 3 racks -> mainframes -> modules -> channels
  * 20 logical controlled units (channel level) with varied fault profiles
    (nominal / flaky / offline / warning / alarm) so the dashboard is alive
  * command_templates table synced from the validated STANDARD_TEMPLATES
  * 2 saved profiles, a global configuration limit row
  * one APPROVED example scenario:
        Start -> Apply profile -> Enable output -> Wait
              -> Record V/I/P -> Threshold check -> Disable output -> End

Run with:  python -m app.seed     (safe to re-run; it no-ops if already seeded)

Also applies TimescaleDB continuous-aggregate + retention policies.
"""
from __future__ import annotations

import logging

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.drivers.templates import STANDARD_TEMPLATES
from app.models import (
    Channel,
    CommandTemplateRow,
    ConfigurationLimit,
    ConnectionProfile,
    Device,
    Mainframe,
    Module,
    Permission,
    Rack,
    Role,
    SavedProfile,
    Scenario,
    ScenarioEdge,
    ScenarioNode,
    ScenarioVersion,
    User,
)
from app.security import ROLE_PERMISSIONS

log = logging.getLogger("sas.seed")

# permission_code -> human description
PERMISSION_DESCRIPTIONS = {
    "view": "View dashboards, measurements, alarms, reports",
    "run_scenario": "Run approved scenarios and routine control functions",
    "control_output": "Toggle output and set parameters within soft limits",
    "approve_scenario": "Approve scenarios, change limits, multi-device actions",
    "admin": "Configure devices, VISA resources, users, retention, maintenance console",
}

# demo user per role -- usernames match the X-Dev-User dev-auth header values
DEMO_USERS = [
    ("observer", "Olivia Observer", "observer"),
    ("operator", "Omar Operator", "operator"),
    ("supervisor", "Sara Supervisor", "supervisor"),
    ("administrator", "Adam Administrator", "administrator"),
]

# 20 logical units. Index -> fault profile (everything else is nominal).
FAULT_OVERRIDES = {5: "flaky", 11: "flaky", 8: "offline", 14: "warning", 17: "alarm"}

# How the 20 channel-level devices are distributed across the 3 racks.
# (rack_name, mainframe_name, [(module_slot, channels_per_module), ...])
RACK_LAYOUT = [
    ("Rack A - Thermal Vacuum", "MF-A1", [(1, 4), (2, 4)]),   # 8 units
    ("Rack B - Ambient Bench", "MF-B1", [(1, 4), (2, 4)]),    # 8 units
    ("Rack C - Integration", "MF-C1", [(1, 4)]),              # 4 units
]


def seed() -> None:
    engine = create_engine(settings.database_url_sync, future=True)
    with Session(engine) as s:
        if s.scalar(select(Rack).limit(1)) is not None:
            log.info("database already seeded -- skipping")
            return
        _seed_rbac(s)
        _seed_templates(s)
        _seed_profiles_and_limits(s)
        devices = _seed_topology(s)
        _seed_example_scenario(s)
        s.commit()
        log.info("seed complete: %d logical units across %d racks",
                 len(devices), len(RACK_LAYOUT))

    # TimescaleDB policies (continuous aggregate + retention) -- autocommit.
    try:
        from app.timescale import apply_timescale_policies
        apply_timescale_policies()
    except Exception as exc:  # noqa: BLE001
        log.warning("timescale policies not applied (%s): %s", type(exc).__name__, exc)


def _seed_rbac(s: Session) -> None:
    perms = {code: Permission(code=code, description=desc)
             for code, desc in PERMISSION_DESCRIPTIONS.items()}
    s.add_all(perms.values())
    s.flush()

    roles: dict[str, Role] = {}
    for role_name, codes in ROLE_PERMISSIONS.items():
        role = Role(name=role_name, description=f"{role_name} role")
        role.permissions = [perms[c] for c in codes]
        s.add(role)
        roles[role_name] = role
    s.flush()

    for username, full_name, role_name in DEMO_USERS:
        s.add(User(username=username, full_name=full_name,
                   email=f"{username}@lab.local", is_active=True,
                   role_id=roles[role_name].id))
    s.flush()
    log.info("seeded %d permissions, %d roles, %d users",
             len(perms), len(roles), len(DEMO_USERS))


def _seed_templates(s: Session) -> None:
    for t in STANDARD_TEMPLATES:
        s.add(CommandTemplateRow(
            template_id=t.id, title=t.title, description=t.description,
            hazardous=t.hazardous, requires_confirmation=t.requires_confirmation,
            idempotent=t.idempotent, parameters=t.parameters))
    s.flush()
    log.info("seeded %d command templates", len(STANDARD_TEMPLATES))


def _seed_profiles_and_limits(s: Session) -> None:
    s.add_all([
        SavedProfile(
            name="Standard Panel A",
            description="Nominal triple-junction panel operating point.",
            params={"isc_a": 8.0, "imp_a": 7.3, "voc_v": 100.0, "vmp_v": 82.0}),
        SavedProfile(
            name="Low-Irradiance Eclipse",
            description="Reduced current to emulate partial eclipse.",
            params={"isc_a": 3.2, "imp_a": 2.9, "voc_v": 96.0, "vmp_v": 78.0}),
    ])
    s.add(ConfigurationLimit(
        scope="global", max_voltage_v=settings.max_voltage_v,
        max_current_a=settings.max_current_a, updated_by="seed"))
    s.flush()


def _seed_topology(s: Session) -> list[Device]:
    devices: list[Device] = []
    unit_index = 0
    for rack_pos, (rack_name, mf_name, modules) in enumerate(RACK_LAYOUT):
        rack = Rack(name=rack_name, location="Lab Hall 1", position=rack_pos)
        s.add(rack)
        s.flush()
        mf = Mainframe(rack_id=rack.id, name=mf_name, model="generic-mainframe")
        s.add(mf)
        s.flush()
        for slot, n_channels in modules:
            module = Module(mainframe_id=mf.id, slot=slot, name=f"Module {slot}")
            s.add(module)
            s.flush()
            for ch_idx in range(1, n_channels + 1):
                channel = Channel(module_id=module.id, index=ch_idx,
                                  name=f"CH{ch_idx}")
                s.add(channel)
                s.flush()

                fault = FAULT_OVERRIDES.get(unit_index, "nominal")
                profile = ConnectionProfile(
                    name=f"{mf_name}-S{slot}-CH{ch_idx}",
                    driver_kind="mock",          # SAFETY: mock until hardware verified
                    connection_type="SIM",
                    # placeholder address; unused while driver_kind == mock
                    visa_resource=f"TCPIP0::192.168.10.{20 + unit_index}::inst0::INSTR",
                    fault_profile=fault,
                    extra={"note": "SIMULATION MODE - placeholder VISA resource"})
                s.add(profile)
                s.flush()

                device = Device(
                    name=f"SAS-{chr(65 + rack_pos)}{slot}-{ch_idx:02d}",
                    rack_id=rack.id, mainframe_id=mf.id, module_id=module.id,
                    channel_id=channel.id, level="channel",
                    connection_profile_id=profile.id,
                    last_state={"device_state": "offline"})
                s.add(device)
                devices.append(device)
                unit_index += 1
    s.flush()
    log.info("seeded topology: %d devices", len(devices))
    return devices


def _seed_example_scenario(s: Session) -> None:
    scenario = Scenario(
        name="Panel Stabilisation & Verification",
        description=("Configure a standard panel profile, enable output, wait for "
                     "stabilisation, record V/I/P, verify the power threshold, then "
                     "safely disable output."),
        current_version=1)
    s.add(scenario)
    s.flush()

    version = ScenarioVersion(
        scenario_id=scenario.id, version=1, status="approved",
        approved_by="supervisor")
    s.add(version)
    s.flush()

    # (node_key, type, label, x, y, config)
    nodes = [
        ("start", "start", "Start", 0, 120, {}),
        ("cfg", "apply_profile", "Apply Profile", 180, 120,
         {"profile": "Standard Panel A",
          "params": {"isc_a": 8.0, "imp_a": 7.3, "voc_v": 100.0, "vmp_v": 82.0}}),
        ("on", "set_output_state", "Enable Output", 360, 120, {"enabled": True}),
        ("wait", "wait", "Wait 3s", 540, 120, {"seconds": 3}),
        ("rec", "record_measurement", "Record V/I/P", 720, 120, {}),
        ("thr", "threshold_check", "Power >= 10W", 900, 120,
         {"field": "power_w", "op": ">=", "value": 10.0}),
        ("off", "set_output_state", "Disable Output", 1080, 120, {"enabled": False}),
        ("end", "end", "End", 1260, 120, {}),
    ]
    for key, ntype, label, x, y, cfg in nodes:
        s.add(ScenarioNode(version_id=version.id, node_key=key, type=ntype,
                           label=label, x=x, y=y, config=cfg))

    edge_pairs = [("start", "cfg"), ("cfg", "on"), ("on", "wait"),
                  ("wait", "rec"), ("rec", "thr"), ("thr", "off"), ("off", "end")]
    for i, (src, dst) in enumerate(edge_pairs):
        s.add(ScenarioEdge(version_id=version.id, edge_key=f"e{i}",
                           source=src, target=dst))
    s.flush()
    log.info("seeded example scenario with %d nodes", len(nodes))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s %(message)s")
    seed()
