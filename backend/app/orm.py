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
    __tablename__ = "units"
    name = Column(String, primary_key=True)
    rack_id = Column(String, ForeignKey("racks.id"), nullable=False)
    slot = Column(Integer, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)   # administrative: included in the fleet at all
    online = Column(Boolean, nullable=False, default=True)    # comms/connection state
    output = Column(Boolean, nullable=False, default=False)   # energised or not
    alarm = Column(String, nullable=False, default="normal")  # normal | warning | offline
    voltage_setpoint = Column(Float, nullable=False, default=28.0)
    current_limit = Column(Float, nullable=False, default=5.0)
    ip_address = Column(String, nullable=False, default="")
    mac_address = Column(String, nullable=False, default="")
    scpi_port = Column(Integer, nullable=False, default=5025)  # reachability probe port — not confirmed against the E4360 Programming Guide, adjust if wrong
    visa = Column(String, nullable=False, default="")  # derived from ip_address — not user-facing
    poll_ms = Column(Integer, nullable=False, default=500)
    firmware = Column(String, nullable=False, default="E4360A · v3.1.2")
    featured = Column(Boolean, nullable=False, default=False)

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
    __tablename__ = "command_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime, nullable=False, index=True)
    user = Column(String, nullable=False)
    device = Column(String, nullable=False)
    template = Column(String, nullable=False)
    status = Column(String, nullable=False)  # OK | WARN | ERR
    latency_ms = Column(Integer, nullable=False, default=0)
    readback = Column(Boolean, nullable=False, default=False)
    correlation_id = Column(String, nullable=False)


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
