"""Prometheus metrics. Exposed at /metrics."""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

command_latency = Histogram(
    "sas_command_latency_seconds", "Instrument command latency",
    ["template_id", "driver_kind"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
commands_total = Counter(
    "sas_commands_total", "Total commands executed", ["template_id", "status"])
failed_commands_total = Counter(
    "sas_failed_commands_total", "Failed/rejected/timed-out commands", ["template_id"])
device_offline = Gauge("sas_devices_offline", "Number of offline devices")
device_online = Gauge("sas_devices_online", "Number of online devices")
active_outputs = Gauge("sas_active_outputs", "Number of enabled outputs")
active_alarms = Gauge("sas_active_alarms", "Number of active (uncleared) alarms")
scenario_runs_total = Counter(
    "sas_scenario_runs_total", "Scenario runs", ["status"])
measurements_written = Counter(
    "sas_measurements_written_total", "Measurement rows persisted")
