from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .db import Base


class Rack(Base):
    __tablename__ = "racks"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    loc = Column(String, nullable=False)
    cap = Column(Integer, nullable=False, default=8)
    units = relationship("Unit", back_populates="rack", cascade="all, delete-orphan")


class Unit(Base):
    """One output channel of one E4360 mainframe. Everything under "mirrored
    from the instrument" is overwritten by the poller every second from what
    the instrument itself reports — the instrument is the source of truth,
    the row is a cache of its last known state."""
    __tablename__ = "units"
    name = Column(String, primary_key=True)
    rack_id = Column(String, ForeignKey("racks.id"), nullable=False)
    slot = Column(Integer, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)   # administrative: included in the fleet at all
    featured = Column(Boolean, nullable=False, default=False)

    # addressing
    ip_address = Column(String, nullable=False, default="")
    mac_address = Column(String, nullable=False, default="")   # label only — not used for communication
    scpi_port = Column(Integer, nullable=False, default=5025)  # used by the "socket" transport only
    transport = Column(String, nullable=False, default="vxi11")  # vxi11 (documented) | socket (opt-in)
    channel = Column(Integer, nullable=False, default=1)       # (@n) channel list suffix
    visa = Column(String, nullable=False, default="")          # derived VISA resource string
    poll_ms = Column(Integer, nullable=False, default=1000)
    firmware = Column(String, nullable=False, default="")

    # mirrored from the instrument
    online = Column(Boolean, nullable=False, default=False)    # last poll got a valid SCPI reply
    last_error = Column(String, nullable=False, default="")    # why the last poll failed, verbatim; "" when online
    output = Column(Boolean, nullable=False, default=False)    # OUTP?
    op_mode = Column(String, nullable=False, default="")       # CURR:MODE? -> FIX | SAS | TABL
    voltage_setpoint = Column(Float, nullable=False, default=0.0)  # VOLT? (FIXed mode)
    current_limit = Column(Float, nullable=False, default=0.0)     # CURR? (FIXed mode)
    questionable = Column(Integer, nullable=False, default=0)  # STAT:QUES:COND? bit field
    alarm = Column(String, nullable=False, default="normal")   # normal | warning | offline
    last_voltage = Column(Float, nullable=True)                # MEAS:VOLT? — null when comms are down
    last_current = Column(Float, nullable=True)
    last_power = Column(Float, nullable=True)

    rack = relationship("Rack", back_populates="units")


class Measurement(Base):
    __tablename__ = "measurements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    unit_name = Column(String, ForeignKey("units.name"), nullable=False, index=True)
    ts = Column(DateTime, nullable=False, index=True)
    reachable = Column(Boolean, nullable=False, default=True)
    voltage = Column(Float, nullable=True)
    current = Column(Float, nullable=True)
    power = Column(Float, nullable=True)
    quality = Column(String, nullable=False, default="ok")  # ok | no_reading


class CommandHistoryRow(Base):
    """Append-only audit log. One row per command actually dispatched to an
    instrument, with the exact SCPI text, what came back, and how it ended."""
    __tablename__ = "command_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, index=True)
    user = Column(String, nullable=False)
    device = Column(String, nullable=False)
    template = Column(String, nullable=False)
    status = Column(String, nullable=False)          # OK | ERR | UNREACHABLE | TIMEOUT
    latency_ms = Column(Integer, nullable=False, default=0)
    readback = Column(Boolean, nullable=False, default=False)  # readback query confirmed the commanded value
    correlation_id = Column(String, nullable=False)
    scpi = Column(String, nullable=False, default="")          # exact program message sent
    response = Column(String, nullable=False, default="")      # readback / query response
    error_code = Column(Integer, nullable=True)                # from SYST:ERR? when the instrument rejected it
    error_msg = Column(String, nullable=False, default="")


class AlarmRow(Base):
    __tablename__ = "alarms"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False)
    unit_name = Column(String, nullable=False)
    code = Column(String, nullable=False)
    sev = Column(String, nullable=False)  # warning | critical | info
    msg = Column(String, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    ackd = Column(Boolean, nullable=False, default=False)


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"
    id = Column(String, primary_key=True)
    scenario = Column(String, nullable=False)
    version = Column(String, nullable=False)
    status = Column(String, nullable=False)  # Queued | Running | Completed | Aborted | Failed
    dry = Column(Boolean, nullable=False, default=False)
    progress = Column(Integer, nullable=False, default=0)
    targets = Column(String, nullable=False, default="")  # comma-separated unit names
    by = Column(String, nullable=False)
    started = Column(String, nullable=False)
    finished = Column(String, nullable=False, default="—")
    dur = Column(String, nullable=False, default="0s")


class ScenarioRunEvent(Base):
    __tablename__ = "scenario_run_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("scenario_runs.id"), nullable=False, index=True)
    t = Column(String, nullable=False)
    node = Column(String, nullable=False)
    lvl = Column(String, nullable=False)  # ok | info | warn | err
    m = Column(String, nullable=False)
