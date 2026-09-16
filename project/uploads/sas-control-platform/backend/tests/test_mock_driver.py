"""Unit tests for the MockE4360Driver -- pure, no database required."""
from __future__ import annotations

import pytest

from app.drivers.base import CommandStatus, DeviceState, UnsafeParameterError
from app.drivers.mock import MockE4360Driver
from app.drivers.templates import TEMPLATES_BY_ID

LIMITS = {"max_voltage_v": 130.0, "max_current_a": 20.0}


def _driver(profile: str = "nominal", name: str = "dev") -> MockE4360Driver:
    return MockE4360Driver(name, "SIM", LIMITS, fault_profile=profile, seed=1)


async def test_connect_and_identify():
    d = _driver(name="dev-1")
    await d.connect()
    idn = await d.identify()
    assert "Solar Array Simulator" in idn


async def test_output_on_produces_power_off_zeroes_it():
    d = _driver(name="dev-2")
    await d.connect()

    res_on = await d.set_output_state(True)
    assert res_on.status == CommandStatus.COMPLETED
    assert res_on.readback_verified is True

    state = await d.read_state()
    assert state.output_enabled is True
    assert state.device_state == DeviceState.OUTPUT_ENABLED

    m = await d.read_measurements()
    assert m.power_w > 0
    assert pytest.approx(m.power_w, rel=0.05) == m.voltage_v * m.current_a

    res_off = await d.set_output_state(False)
    assert res_off.status == CommandStatus.COMPLETED
    m_off = await d.read_measurements()
    assert m_off.voltage_v == 0.0
    assert m_off.current_a == 0.0


async def test_offline_profile_refuses_connect():
    d = _driver(profile="offline", name="dev-3")
    with pytest.raises(ConnectionError):
        await d.connect()


async def test_offline_state_reports_lost_comms():
    d = _driver(name="dev-3b")
    # never connected
    state = await d.read_state()
    assert state.connected is False
    assert state.comm_health == "lost"
    assert state.device_state == DeviceState.OFFLINE


async def test_alarm_profile_blocks_writes():
    d = _driver(profile="alarm", name="dev-4")
    await d.connect()
    res = await d.set_output_state(True)
    assert res.status == CommandStatus.FAILED
    state = await d.read_state()
    assert state.device_state == DeviceState.ALARM
    assert state.alarm_state == "OVERTEMP"


async def test_warning_profile_surfaces_warning_state():
    d = _driver(profile="warning", name="dev-4w")
    await d.connect()
    state = await d.read_state()
    assert state.device_state == DeviceState.WARNING
    assert state.alarm_state == "FAN_DEGRADED"


async def test_unsafe_voltage_rejected():
    d = _driver(name="dev-5")
    await d.connect()
    tmpl = TEMPLATES_BY_ID["set_voltage"]
    with pytest.raises(UnsafeParameterError):
        await d.execute_validated_command(tmpl, {"voltage_v": 999.0})


async def test_missing_required_param_rejected():
    d = _driver(name="dev-5b")
    await d.connect()
    tmpl = TEMPLATES_BY_ID["set_voltage"]
    with pytest.raises(UnsafeParameterError):
        await d.execute_validated_command(tmpl, {})


async def test_safe_shutdown_disables_output():
    d = _driver(name="dev-6")
    await d.connect()
    await d.set_output_state(True)
    res = await d.safe_shutdown()
    assert res.status == CommandStatus.COMPLETED
    state = await d.read_state()
    assert state.output_enabled is False


async def test_apply_profile_changes_curve():
    d = _driver(name="dev-7")
    await d.connect()
    await d.set_output_state(True)
    await d.apply_profile({"isc_a": 5.0, "imp_a": 4.5, "voc_v": 90.0, "vmp_v": 70.0})
    m = await d.read_measurements()
    # current should now track the new (lower) Imp band
    assert m.current_a <= 5.5


async def test_capabilities_report_simulation():
    d = _driver(name="dev-8")
    caps = d.get_capabilities()
    assert caps.simulation is True
    assert caps.driver_kind == "mock"
    assert caps.supports_solar_array_table is True
    assert len(caps.command_templates) > 0
