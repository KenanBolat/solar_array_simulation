"""Driver registry: chooses Mock vs real driver based on the master switch
and per-device connection profile. Holds one driver instance per device."""
from __future__ import annotations

from app.config import settings
from app.drivers.base import InstrumentDriver
from app.drivers.e4360 import E4360Driver
from app.drivers.mock import MockE4360Driver


class DriverRegistry:
    def __init__(self):
        self._drivers: dict[str, InstrumentDriver] = {}

    def get_or_create(self, device_id: str, *, resource: str, driver_kind: str,
                      fault_profile: str = "nominal",
                      soft_limits: dict[str, float] | None = None) -> InstrumentDriver:
        if device_id in self._drivers:
            return self._drivers[device_id]
        limits = soft_limits or {
            "max_voltage_v": settings.max_voltage_v,
            "max_current_a": settings.max_current_a,
        }
        # SAFETY: real driver only when the master switch is on AND profile asks for it.
        if settings.hardware_enabled and driver_kind == "e4360":
            driver: InstrumentDriver = E4360Driver(device_id, resource, limits)
        else:
            driver = MockE4360Driver(device_id, resource, limits, fault_profile=fault_profile)
        self._drivers[device_id] = driver
        return driver

    def get(self, device_id: str) -> InstrumentDriver | None:
        return self._drivers.get(device_id)

    def all(self) -> dict[str, InstrumentDriver]:
        return dict(self._drivers)


_registry: DriverRegistry | None = None


def get_driver_registry() -> DriverRegistry:
    global _registry
    if _registry is None:
        _registry = DriverRegistry()
    return _registry
