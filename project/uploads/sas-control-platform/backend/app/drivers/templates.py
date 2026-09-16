"""Standard validated command templates shared by all drivers.

IMPORTANT: The `scpi` field on each real-hardware mapping lives in
e4360.py and is marked unverified until confirmed against the official
Keysight E4360 programming manual. No manufacturer SCPI syntax is invented
here -- only generic, named, parameter-validated intents.
"""
from __future__ import annotations

from app.config import settings
from app.drivers.base import CommandTemplate

STANDARD_TEMPLATES: list[CommandTemplate] = [
    CommandTemplate(
        id="identify",
        title="Query Device Identity",
        description="Request *IDN-style identity from the instrument.",
        idempotent=True,
    ),
    CommandTemplate(
        id="read_measurements",
        title="Refresh Measurements",
        description="Read voltage, current and power.",
        idempotent=True,
    ),
    CommandTemplate(
        id="set_voltage",
        title="Set Output Voltage",
        description="Set the programmed output voltage (Vmp/Voc context).",
        hazardous=True,
        requires_confirmation=True,
        parameters={
            "voltage_v": {"type": "float", "min": 0.0, "max": settings.max_voltage_v,
                          "unit": "V", "required": True},
        },
    ),
    CommandTemplate(
        id="set_current_limit",
        title="Set Current Limit",
        description="Set the programmed current limit (Imp/Isc context).",
        hazardous=True,
        requires_confirmation=True,
        parameters={
            "current_a": {"type": "float", "min": 0.0, "max": settings.max_current_a,
                          "unit": "A", "required": True},
        },
    ),
    CommandTemplate(
        id="configure_sas_table",
        title="Configure Solar-Array Simulation Parameters",
        description="Set the SAS I-V curve parameters (Isc, Imp, Voc, Vmp).",
        hazardous=True,
        requires_confirmation=True,
        parameters={
            "isc_a": {"type": "float", "min": 0.0, "max": settings.max_current_a, "unit": "A", "required": True},
            "imp_a": {"type": "float", "min": 0.0, "max": settings.max_current_a, "unit": "A", "required": True},
            "voc_v": {"type": "float", "min": 0.0, "max": settings.max_voltage_v, "unit": "V", "required": True},
            "vmp_v": {"type": "float", "min": 0.0, "max": settings.max_voltage_v, "unit": "V", "required": True},
        },
    ),
    CommandTemplate(
        id="output_on",
        title="Enable Output",
        description="Enable the output channel.",
        hazardous=True,
        requires_confirmation=True,
    ),
    CommandTemplate(
        id="output_off",
        title="Disable Output",
        description="Disable the output channel.",
        hazardous=True,
        requires_confirmation=True,
    ),
    CommandTemplate(
        id="apply_profile",
        title="Apply Named Configuration Profile",
        description="Apply a saved profile (SAS table + limits).",
        hazardous=True,
        requires_confirmation=True,
    ),
    CommandTemplate(
        id="safe_shutdown",
        title="Emergency Safe Shutdown",
        description="Attempt to disable output and bring device to a safe state.",
        hazardous=True,
        requires_confirmation=True,
    ),
]

TEMPLATES_BY_ID = {t.id: t for t in STANDARD_TEMPLATES}
CAPABILITY_MAP_VERSION = "0.1.0"
