"""Mock instrument driver.

This is a simulation only — it never opens a VISA/socket session and never
talks to real hardware. There is no SCPI transport here at all: values are
computed in software to make the UI feel alive. Wiring this platform to a
real Keysight E4360A requires a separate, verified hardware driver; that is
explicitly out of scope for this build (see README).
"""
import math
import time


def name_hash(name: str) -> int:
    h = 0
    for ch in name:
        h = (h * 31 + ord(ch)) % 997
    return h


def compute_live_values(name: str, online: bool, output: bool, voltage_setpoint: float, current_limit: float,
                         featured: bool = False, featured_v=None, featured_i=None, featured_p=None):
    """Return (v, i, p) for a unit given its current commanded state."""
    if featured and output:
        return featured_v, featured_i, featured_p
    if not online or not output:
        return 0.0, 0.0, 0.0
    h = name_hash(name)
    jitter = math.sin(time.time() / 3.0 + h) * 0.03
    v = min(voltage_setpoint, 27.4 + (h % 9) * 0.18) + jitter
    i = min(current_limit, 3.6 + (h % 7) * 0.16) + jitter * 0.5
    v = max(0.0, v)
    i = max(0.0, i)
    p = v * i
    return round(v, 3), round(i, 3), round(p, 3)
