"""Seed a REAL two-unit hardware configuration.

Replaces the 20-unit simulation demo with your actual bench: one rack, one
mainframe, two channel-level units addressed over LAN raw socket, and a single
operator account.

    cd backend
    python -m app.seed_hardware              # create (mock driver, safe)
    python -m app.seed_hardware --reset      # wipe existing topology first
    python -m app.seed_hardware --real       # bind units to the e4360 driver

Ordering with the rest of bring-up:

  1. Fill in UNITS below with your real IPs, slots, channels and ratings.
  2. Run WITHOUT --real first. Units appear in the UI on the mock driver, so
     you can confirm the topology reads correctly with zero hardware risk.
  3. Verify SCPI strings in drivers/e4360.py and pass scripts/commission.py.
  4. Re-run with --real, then set SAS_HARDWARE_ENABLED=true.

The script refuses to run while UNITS still contains placeholder values.
"""
from __future__ import annotations

import argparse
import logging

from sqlalchemy import create_engine, delete, select
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
    User,
)
from app.security import ROLE_PERMISSIONS

log = logging.getLogger("sas.seed_hardware")

# =============================================================================
# EDIT THIS BLOCK
# =============================================================================

RACK = {"name": "Bench Rack", "location": "Lab — bench", "position": 0}

MAINFRAME = {
    "name": "MF-1",
    # From the label on the chassis, e.g. "E4360A".
    "model": "FILL_ME_mainframe_model",
}

# One entry per controlled output. `ip` is the instrument's address; `port` is
# the raw-socket SCPI port (5025 unless your instrument documents otherwise).
#
# max_voltage_v / max_current_a are the PER-CHANNEL module ratings and become
# this unit's soft limits. They are advisory — set hardware OVP/OCP on the
# instrument itself as the real backstop.
UNITS = [
    {
        "name": "SAS-01",
        "module_model": "FILL_ME_module_model",
        "slot": 1,
        "channel": 1,
        "ip": "FILL_ME_IP_1",
        "port": 5025,
        "max_voltage_v": 130.0,
        "max_current_a": 5.0,
    },
    {
        "name": "SAS-02",
        "module_model": "FILL_ME_module_model",
        "slot": 2,
        "channel": 1,
        "ip": "FILL_ME_IP_2",
        "port": 5025,
        "max_voltage_v": 130.0,
        "max_current_a": 5.0,
    },
]

# Single-user operation. `administrator` so one person can both configure and
# control; the audit log records this username as the actor for every command.
OPERATOR = {
    "username": "operator",
    "full_name": "Lab Operator",
    "email": "operator@lab.local",
    "role": "administrator",
}

# =============================================================================


def visa_resource(unit: dict) -> str:
    """Raw-socket VISA resource string for a unit."""
    return f"TCPIP0::{unit['ip']}::{unit['port']}::SOCKET"


def check_placeholders() -> list[str]:
    problems: list[str] = []
    if "FILL_ME" in MAINFRAME["model"]:
        problems.append("MAINFRAME['model'] is still a placeholder")
    for u in UNITS:
        for key in ("ip", "module_model"):
            if "FILL_ME" in str(u[key]):
                problems.append(f"{u['name']}: {key} is still a placeholder")
    return problems


def seed_hardware(reset: bool, real: bool) -> int:
    problems = check_placeholders()
    if problems:
        print("\nRefusing to seed — fill in the EDIT THIS BLOCK section first:\n")
        for p in problems:
            print(f"  - {p}")
        print()
        return 1

    driver_kind = "e4360" if real else "mock"
    engine = create_engine(settings.database_url_sync, future=True)

    with Session(engine) as s:
        existing = s.scalar(select(Rack).limit(1))
        if existing is not None and not reset:
            print(
                "\nTopology already present. Re-run with --reset to replace it.\n"
                "  (--reset deletes devices, channels, modules, mainframes and racks;\n"
                "   measurements and audit history are left untouched.)\n"
            )
            return 1

        if reset:
            for model in (Device, Channel, Module, Mainframe, Rack, ConnectionProfile):
                s.execute(delete(model))
            s.flush()
            log.info("cleared existing topology")

        # --- RBAC: only create if absent -----------------------------------
        if s.scalar(select(Permission).limit(1)) is None:
            perms = {
                code: Permission(code=code, description=code)
                for code in {c for codes in ROLE_PERMISSIONS.values() for c in codes}
            }
            s.add_all(perms.values())
            s.flush()
            for role_name, codes in ROLE_PERMISSIONS.items():
                role = Role(name=role_name, description=f"{role_name} role")
                role.permissions = [perms[c] for c in codes]
                s.add(role)
            s.flush()

        role = s.scalar(select(Role).where(Role.name == OPERATOR["role"]))
        if role is None:
            raise RuntimeError(f"role '{OPERATOR['role']}' not found")
        if s.scalar(select(User).where(User.username == OPERATOR["username"])) is None:
            s.add(
                User(
                    username=OPERATOR["username"],
                    full_name=OPERATOR["full_name"],
                    email=OPERATOR["email"],
                    is_active=True,
                    role_id=role.id,
                )
            )
            s.flush()

        # --- command templates ---------------------------------------------
        if s.scalar(select(CommandTemplateRow).limit(1)) is None:
            for t in STANDARD_TEMPLATES:
                s.add(
                    CommandTemplateRow(
                        template_id=t.id,
                        title=t.title,
                        description=t.description,
                        hazardous=t.hazardous,
                        requires_confirmation=t.requires_confirmation,
                        idempotent=t.idempotent,
                        parameters=t.parameters,
                    )
                )
            s.flush()

        # --- limits: global ceiling is the highest per-channel rating -------
        if s.scalar(select(ConfigurationLimit).limit(1)) is None:
            s.add(
                ConfigurationLimit(
                    scope="global",
                    max_voltage_v=max(u["max_voltage_v"] for u in UNITS),
                    max_current_a=max(u["max_current_a"] for u in UNITS),
                    updated_by="seed_hardware",
                )
            )
            s.flush()

        if s.scalar(select(SavedProfile).limit(1)) is None:
            s.add(
                SavedProfile(
                    name="Bench Low-Power Check",
                    description="Deliberately low operating point for commissioning.",
                    params={"isc_a": 0.5, "imp_a": 0.45, "voc_v": 10.0, "vmp_v": 8.0},
                )
            )
            s.flush()

        # --- topology -------------------------------------------------------
        rack = Rack(**RACK)
        s.add(rack)
        s.flush()

        mf = Mainframe(rack_id=rack.id, name=MAINFRAME["name"], model=MAINFRAME["model"])
        s.add(mf)
        s.flush()

        created: list[str] = []
        for u in UNITS:
            module = Module(mainframe_id=mf.id, slot=u["slot"], name=u["module_model"])
            s.add(module)
            s.flush()

            channel = Channel(module_id=module.id, index=u["channel"], name=f"CH{u['channel']}")
            s.add(channel)
            s.flush()

            profile = ConnectionProfile(
                name=f"{MAINFRAME['name']}-S{u['slot']}-CH{u['channel']}",
                driver_kind=driver_kind,
                connection_type="LAN-SOCKET",
                visa_resource=visa_resource(u),
                fault_profile="nominal",
                extra={
                    "channel": u["channel"],
                    "max_voltage_v": u["max_voltage_v"],
                    "max_current_a": u["max_current_a"],
                    "note": (
                        "real hardware, LAN raw socket"
                        if real
                        else "mock driver — topology check only"
                    ),
                },
            )
            s.add(profile)
            s.flush()

            s.add(
                Device(
                    name=u["name"],
                    rack_id=rack.id,
                    mainframe_id=mf.id,
                    module_id=module.id,
                    channel_id=channel.id,
                    level="channel",
                    connection_profile_id=profile.id,
                    last_state={"device_state": "offline"},
                )
            )
            created.append(f"{u['name']}  slot {u['slot']} ch {u['channel']}  {visa_resource(u)}")

        s.commit()

    print("\nSeeded 2-unit hardware topology:\n")
    for line in created:
        print(f"  {line}")
    print(f"\n  driver_kind = {driver_kind}")
    print(f"  operator    = {OPERATOR['username']} ({OPERATOR['role']})")
    if real:
        print(
            "\n  Units are bound to the e4360 driver. They stay on the mock driver\n"
            "  until SAS_HARDWARE_ENABLED=true, and every unverified SCPI command\n"
            "  is still refused by the driver.\n"
        )
    else:
        print("\n  Mock driver — no hardware will be contacted. Safe to explore.\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reset", action="store_true", help="delete existing topology first")
    ap.add_argument("--real", action="store_true", help="bind units to the e4360 driver")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    return seed_hardware(args.reset, args.real)


if __name__ == "__main__":
    raise SystemExit(main())
