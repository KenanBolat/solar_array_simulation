from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select, text

from app.config import settings
from app.db import engine
from app.drivers.e4360 import verification_report
from app.drivers.templates import CAPABILITY_MAP_VERSION, STANDARD_TEMPLATES

router = APIRouter(tags=["system"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/ready")
async def ready():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db = True
    except Exception:
        db = False
    return {"status": "ready" if db else "degraded", "database": db}


@router.get("/api/meta")
async def meta():
    return {
        "app_name": settings.app_name,
        "environment": settings.environment,
        "simulation_mode": not settings.hardware_enabled,
        "simulation_banner": settings.simulation_banner,
        "capability_map_version": CAPABILITY_MAP_VERSION,
        "soft_limits": {
            "max_voltage_v": settings.max_voltage_v,
            "max_current_a": settings.max_current_a,
        },
    }


@router.get("/api/hardware-readiness")
async def hardware_readiness():
    """Pre-flight state for connecting real instruments.

    Read-only and side-effect free: reports which SCPI operations have been
    verified against the programming manual, which command templates are
    therefore live, and which configuration gates are still closed. Safe to
    poll from the UI at any time, including on a production bench.
    """
    ops = verification_report()

    # A template is live only if every operation it depends on is verified.
    deps: dict[str, tuple[str, ...]] = {
        "identify": ("identify",),
        "read_measurements": ("read_voltage", "read_current"),
        "set_voltage": ("set_voltage",),
        "set_current_limit": ("set_current_limit",),
        "configure_sas_table": ("sas_isc", "sas_imp", "sas_voc", "sas_vmp"),
        "output_on": ("output_on",),
        "output_off": ("output_off",),
        "apply_profile": ("sas_isc", "sas_imp", "sas_voc", "sas_vmp"),
        "safe_shutdown": ("output_off",),
    }
    by_op = {o["op"]: o for o in ops}
    templates = []
    for t in STANDARD_TEMPLATES:
        required = deps.get(t.id, ())
        missing = [d for d in required if not by_op.get(d, {}).get("verified")]
        templates.append(
            {
                "id": t.id,
                "title": t.title,
                "hazardous": t.hazardous,
                "live": bool(required) and not missing,
                "blocked_by": missing,
            }
        )

    # Configuration gates, in the order they must be cleared.
    unresolved_placeholders = 0
    lan_socket_units = 0
    real_driver_units = 0
    try:
        from app.models import ConnectionProfile

        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    select(
                        ConnectionProfile.driver_kind,
                        ConnectionProfile.connection_type,
                        ConnectionProfile.visa_resource,
                    )
                )
            ).all()
        for driver_kind, connection_type, visa in rows:
            if driver_kind == "e4360":
                real_driver_units += 1
            if (connection_type or "").upper().startswith("LAN"):
                lan_socket_units += 1
            if not visa or "FILL_ME" in visa or "192.168.10." in visa:
                unresolved_placeholders += 1
    except Exception:
        pass

    verified_ops = sum(1 for o in ops if o["verified"])
    live_templates = sum(1 for t in templates if t["live"])

    gates = [
        {
            "id": "scpi_verified",
            "label": "SCPI operations verified against the manual",
            "ok": verified_ops == len(ops),
            "detail": f"{verified_ops} of {len(ops)} operations verified",
        },
        {
            "id": "visa_resources",
            "label": "Real VISA resource strings configured",
            "ok": unresolved_placeholders == 0 and bool(lan_socket_units),
            "detail": (
                f"{unresolved_placeholders} unit(s) still on placeholder addresses"
                if unresolved_placeholders
                else f"{lan_socket_units} unit(s) on LAN transport"
            ),
        },
        {
            "id": "driver_bound",
            "label": "Units bound to the real driver",
            "ok": real_driver_units > 0,
            "detail": f"{real_driver_units} unit(s) using the e4360 driver",
        },
        {
            "id": "hardware_enabled",
            "label": "Hardware master switch enabled",
            "ok": settings.hardware_enabled,
            "detail": (
                "SAS_HARDWARE_ENABLED=true"
                if settings.hardware_enabled
                else "SAS_HARDWARE_ENABLED=false — all devices forced to mock"
            ),
        },
        {
            "id": "auth_hardened",
            "label": "Authentication hardened for a shared network",
            "ok": not settings.dev_auth_enabled
            and settings.jwt_secret != "change-me-in-production",
            "detail": (
                "dev auth is ON — any client can impersonate a user"
                if settings.dev_auth_enabled
                else (
                    "default JWT secret still in use"
                    if settings.jwt_secret == "change-me-in-production"
                    else "dev auth off, secret changed"
                )
            ),
        },
    ]

    return {
        "simulation_mode": not settings.hardware_enabled,
        "capability_map_version": CAPABILITY_MAP_VERSION,
        "operations": ops,
        "templates": templates,
        "gates": gates,
        "summary": {
            "verified_ops": verified_ops,
            "total_ops": len(ops),
            "live_templates": live_templates,
            "total_templates": len(templates),
            "gates_open": sum(1 for g in gates if g["ok"]),
            "total_gates": len(gates),
        },
    }
