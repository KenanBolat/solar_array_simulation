"""Mock instrument driver — with one real exception.

Measurement *values* are still computed in software (no verified SCPI query
syntax exists for this instrument yet — see README/HARDWARE.md). But
`check_reachable` is a genuine network operation: a plain TCP connect to the
unit's stored IP:port, no SCPI sent. It answers "is anything listening
there," nothing more. This is deliberately the smallest possible real step
toward hardware integration — a safe, read-only reachability signal — while
the actual telemetry stays simulated until real command syntax is available.
"""
import math
import socket
import time

REACHABILITY_TIMEOUT_S = 0.6


def name_hash(name: str) -> int:
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) % 997
    return h


def check_reachable(ip_address: str, port: int) -> bool:
    """Real TCP connect probe — no SCPI, no data exchanged. True only if
    something actually accepted the connection within the timeout."""
    if not ip_address:
        return False
    try:
        with socket.create_connection((ip_address, port), timeout=REACHABILITY_TIMEOUT_S):
            return True
    except OSError:
        return False


def compute_live_values(name: str, online: bool, output: bool, voltage_setpoint: float, current_limit: float,
                         featured: bool = False, featured_v=None, featured_i=None, featured_p=None):
    """Return (v, i, p) for a unit given its current commanded state.

    (None, None, None) means "no reading" — comms are down, nothing was
    retrieved. (0.0, 0.0, 0.0) is a real reading of a de-energised output.
    These are not the same thing and callers must not conflate them.

    `online` here should already reflect a real reachability check
    (check_reachable) — this function only decides what a *reachable* unit
    would be reading, since it has no way to talk SCPI to get a real value.
    """
    if not online:
        return None, None, None
    if featured and output:
        return featured_v, featured_i, featured_p
    if not output:
        return 0.0, 0.0, 0.0
    h = name_hash(name)
    jitter = math.sin(time.time() / 3.0 + h) * 0.03
    v = min(voltage_setpoint, 27.4 + (h % 9) * 0.18) + jitter
    i = min(current_limit, 3.6 + (h % 7) * 0.16) + jitter * 0.5
    v = max(0.0, v)
    i = max(0.0, i)
    p = v * i
    return round(v, 3), round(i, 3), round(p, 3)
