#!/usr/bin/env python3
"""Commissioning walk for ONE unit on real hardware.

Runs the instrument through its command set in ascending order of consequence,
verifying each step before the next is offered. Stops at the first failure.
Nothing that can energise an output happens without a typed confirmation.

Run it OUTSIDE the application: no database, no API, no scenario engine. It
talks to one instrument through the same driver the platform uses, so a pass
here means the platform's command path will work.

    cd backend
    python scripts/commission.py --resource "TCPIP0::192.168.10.21::5025::SOCKET"

    # once setpoint strings are verified and the load is disconnected:
    python scripts/commission.py --resource "..." --allow-output

Order of operations:
    1. table         report which SCPI strings are filled in
    2. connect       open the socket, confirm termination settings
    3. identify      *IDN?
    4. errors        read the error queue
    5. measure       read V / I / P with output OFF
    6. setpoints     write a LOW voltage and current limit, verify readback
    7. output        enable, measure, disable   [--allow-output only]
    8. shutdown      exercise the safe-shutdown path

PRECONDITION for steps 6-8: the output must be physically DISCONNECTED from
any panel-under-test or load.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

sys.path.insert(0, ".")

from app.drivers.base import CommandStatus, DriverError  # noqa: E402
from app.drivers.e4360 import E4360Driver, verification_report  # noqa: E402
from app.drivers.templates import TEMPLATES_BY_ID  # noqa: E402

# Deliberately low commissioning setpoints — well inside any plausible rating.
COMMISSION_VOLTS = 5.0
COMMISSION_AMPS = 0.5


class Stop(Exception):
    """Abort the walk."""


def ok(msg: str) -> None:
    print(f"  \033[32mPASS\033[0m  {msg}")


def bad(msg: str) -> None:
    print(f"  \033[31mFAIL\033[0m  {msg}")


def skip(msg: str) -> None:
    print(f"  \033[33mSKIP\033[0m  {msg}")


def info(msg: str) -> None:
    print(f"        {msg}")


def step(n: int, title: str) -> None:
    print(f"\n\033[1m[{n}] {title}\033[0m")


def confirm(prompt: str, phrase: str) -> bool:
    print(f"\n  \033[33m{prompt}\033[0m")
    got = input(f"  Type {phrase} to proceed (anything else aborts): ").strip()
    return got == phrase


def show_result(label: str, res) -> None:
    line = f"{label}: {res.status.value}"
    if res.scpi_sent:
        line += f"\n        sent     {res.scpi_sent}"
    if res.scpi_response is not None:
        line += f"\n        response {res.scpi_response}"
    line += f"\n        readback {'verified' if res.readback_verified else 'NOT verified'}"
    if res.message:
        line += f"\n        note     {res.message}"
    if res.status is CommandStatus.COMPLETED:
        ok(line)
    else:
        bad(line)
        raise Stop(res.message or f"{label} did not complete")


async def walk(resource: str, channel: str, allow_output: bool) -> None:
    # ---------------------------------------------------------------- 1. table
    step(1, "SCPI verification table")
    report = verification_report()
    unverified = [r for r in report if not r["verified"]]
    for r in report:
        mark = "verified" if r["verified"] else "NOT verified"
        kinds = ",".join(
            k for k, present in (
                ("write", r["has_write"]),
                ("query", r["has_query"]),
                ("readback", r["has_readback"]),
            ) if present
        ) or "nothing filled in"
        print(f"        {r['op']:<20} {mark:<13} [{kinds}]")
    if unverified:
        info(f"{len(unverified)} of {len(report)} operations still unverified.")
        info("Unverified operations are refused by the driver — that is expected")
        info("until you have filled them in from the manual.")

    # -------------------------------------------------------------- 2. connect
    step(2, "Connect")
    driver = E4360Driver(
        device_id="commission",
        resource=resource,
        soft_limits={"max_voltage_v": 130.0, "max_current_a": 20.0},
        channel=channel,
    )
    try:
        await driver.connect()
        ok(f"opened {resource}")
    except DriverError as exc:
        bad(str(exc))
        info("For SOCKET resources check: port (usually 5025), the instrument's")
        info("LAN config, firewall between this host and the instrument, and that")
        info("read/write termination are newline (the driver sets these).")
        raise Stop("cannot continue without a connection") from exc

    try:
        # ----------------------------------------------------------- 3. identify
        step(3, "Identify")
        ident = await driver.identify()
        ok(f"*IDN? -> {ident}")

        # ------------------------------------------------------------ 4. errors
        step(4, "Error queue")
        err = await driver._check_error_queue()
        if err is None:
            ok("error queue clean (or SYST:ERR? unsupported)")
        else:
            bad(f"instrument reports: {err}")
            raise Stop("clear the instrument error state before continuing")

        # ----------------------------------------------------------- 5. measure
        step(5, "Read measurements (output should be OFF)")
        try:
            m = await driver.read_measurements()
            ok(f"V={m.voltage_v} A={m.current_a} W={m.power_w} output={m.output_enabled}")
            if m.output_enabled:
                bad("output reads ENABLED at the start of commissioning")
                raise Stop("disable the output before commissioning")
        except DriverError as exc:
            skip(f"measurement read unavailable: {exc}")

        # --------------------------------------------------------- 6. setpoints
        step(6, "Setpoint write + readback")
        for tid, params, expect in (
            ("set_voltage", {"voltage_v": COMMISSION_VOLTS}, COMMISSION_VOLTS),
            ("set_current_limit", {"current_a": COMMISSION_AMPS}, COMMISSION_AMPS),
        ):
            try:
                res = await driver.execute_validated_command(TEMPLATES_BY_ID[tid], params)
            except DriverError as exc:
                skip(f"{tid}: {exc}")
                continue
            show_result(f"{tid} -> {expect}", res)
            if not res.readback_verified:
                bad(f"{tid} readback did not confirm {expect}")
                raise Stop(
                    "a setpoint that cannot be read back must not be trusted — "
                    "check the readback query string for this operation"
                )

        # ------------------------------------------------------------ 7. output
        step(7, "Output enable / disable")
        if not allow_output:
            skip("output test not requested (pass --allow-output to include it)")
        else:
            if not confirm(
                "This ENERGISES the output. Confirm the output terminals are "
                "DISCONNECTED from any panel or load, and that hardware OVP/OCP "
                "are set.",
                "DISCONNECTED",
            ):
                raise Stop("output test declined by operator")
            try:
                res = await driver.set_output_state(True)
                show_result("output_on", res)
                await asyncio.sleep(1.0)
                m = await driver.read_measurements()
                ok(f"with output on: V={m.voltage_v} A={m.current_a} W={m.power_w}")
            finally:
                # Always attempt to disable, even if the measurement raised.
                res_off = await driver.set_output_state(False)
                show_result("output_off", res_off)

        # ---------------------------------------------------------- 8. shutdown
        step(8, "Safe shutdown path")
        try:
            res = await driver.safe_shutdown()
            show_result("safe_shutdown", res)
        except DriverError as exc:
            skip(f"safe_shutdown unavailable: {exc}")

    finally:
        await driver.disconnect()
        print("\n        disconnected")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--resource",
        required=True,
        help='VISA resource, e.g. "TCPIP0::192.168.10.21::5025::SOCKET"',
    )
    ap.add_argument("--channel", default="1", help="channel selector substituted for {ch}")
    ap.add_argument(
        "--allow-output",
        action="store_true",
        help="include the output-enable test (requires a typed confirmation)",
    )
    args = ap.parse_args()

    print("=" * 70)
    print(" E4360 commissioning walk")
    print(f" resource {args.resource}")
    print(f" channel  {args.channel}")
    print("=" * 70)

    try:
        asyncio.run(walk(args.resource, args.channel, args.allow_output))
    except Stop as exc:
        print(f"\n\033[31mSTOPPED\033[0m {exc}\n")
        return 1
    except KeyboardInterrupt:
        print("\n\033[33mINTERRUPTED\033[0m — verify the output is disabled.\n")
        return 130

    print("\n\033[32mWALK COMPLETE\033[0m")
    print("Every attempted step passed. Steps reported SKIP are still unverified")
    print("in the SCPI table and remain blocked in the platform.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
