from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
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
    name = Column(String, primary_key=True)          # unique key, e.g. "SAS-01" or "SAS-01-CH2"
    mainframe_name = Column(String, nullable=False, default="")  # the instrument, e.g. "SAS-01" — shared by its channels
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
    sas_isc = Column(Float, nullable=True)   # CURR:SAS:ISC? — the four coupled SAS curve
    sas_imp = Column(Float, nullable=True)   # CURR:SAS:IMP?   parameters, read back in SAS mode
    sas_vmp = Column(Float, nullable=True)   # VOLT:SAS:VMP?
    sas_voc = Column(Float, nullable=True)   # VOLT:SAS:VOC?
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


class Preset(Base):
    """A named operating point stored by the platform (not in the instrument's
    own 2-slot non-volatile memory — see *SAV/*RCL, which has a documented
    write-cycle limit). Applying one dispatches the same SCPI the manual
    controls do: VOLT/CURR for a FIX preset, the four coupled curve
    parameters for a SAS preset."""
    __tablename__ = "presets"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    mode = Column(String, nullable=False, default="FIX")  # FIX | SAS
    volt = Column(Float, nullable=False, default=0.0)     # FIX
    curr = Column(Float, nullable=False, default=0.0)     # FIX
    isc = Column(Float, nullable=False, default=0.0)      # SAS
    imp = Column(Float, nullable=False, default=0.0)
    vmp = Column(Float, nullable=False, default=0.0)
    voc = Column(Float, nullable=False, default=0.0)
    enabled = Column(Boolean, nullable=False, default=True)  # disabled presets stay stored but can't be applied
    note = Column(String, nullable=False, default="")
    created = Column(DateTime, nullable=False)


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


class Scenario(Base):
    __tablename__ = "scenarios"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False, default="v1.0")
    state = Column(String, nullable=False, default="DRAFT")
    target_unit = Column(String, nullable=False, default="")  # empty = the featured unit at run time
    nodes = relationship("ScenarioNode", back_populates="scenario", cascade="all, delete-orphan")
    edges = relationship("ScenarioEdge", back_populates="scenario", cascade="all, delete-orphan")


class ScenarioNode(Base):
    """One step of a scenario. `params` is a JSON object whose shape is defined
    by the node's type in data.NODE_TYPES — that registry is what lets the UI
    render a typed editor and what the runner reads when dispatching."""
    __tablename__ = "scenario_nodes"
    id = Column(String, primary_key=True)              # unique across scenarios
    scenario_id = Column(String, ForeignKey("scenarios.id"), nullable=False, index=True)
    type = Column(String, nullable=False)              # key into data.NODE_TYPES
    label = Column(String, nullable=False, default="")  # operator-editable title
    x = Column(Integer, nullable=False, default=0)
    y = Column(Integer, nullable=False, default=0)
    params = Column(Text, nullable=False, default="{}")
    scenario = relationship("Scenario", back_populates="nodes")


class ScenarioEdge(Base):
    __tablename__ = "scenario_edges"
    id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(String, ForeignKey("scenarios.id"), nullable=False, index=True)
    src = Column(String, nullable=False)
    dst = Column(String, nullable=False)
    fail = Column(Boolean, nullable=False, default=False)  # the branch taken when a check fails / a step errors
    scenario = relationship("Scenario", back_populates="edges")


class ScenarioRun(Base):
    __tablename__ = "scenario_runs"
    id = Column(String, primary_key=True)
    scenario = Column(String, nullable=False)
    scenario_id = Column(String, nullable=False, default="")
    version = Column(String, nullable=False)
    status = Column(String, nullable=False)  # Queued | Running | Completed | Aborted | Failed
    dry = Column(Boolean, nullable=False, default=False)
    progress = Column(Integer, nullable=False, default=0)
    targets = Column(String, nullable=False, default="")  # comma-separated unit names
    by = Column(String, nullable=False)
    started = Column(String, nullable=False)
    finished = Column(String, nullable=False, default="—")
    dur = Column(String, nullable=False, default="0s")
    # live view: which block is running, what every block's state is, and the
    # clock the time indicator reads from
    current_node = Column(String, nullable=False, default="")
    node_states = Column(Text, nullable=False, default="{}")  # {nodeId: ready|running|done|error|skipped}
    started_ms = Column(Integer, nullable=True)
    ended_ms = Column(Integer, nullable=True)
    est_ms = Column(Integer, nullable=False, default=0)


class ScenarioRunEvent(Base):
    __tablename__ = "scenario_run_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("scenario_runs.id"), nullable=False, index=True)
    t = Column(String, nullable=False)
    node = Column(String, nullable=False)
    lvl = Column(String, nullable=False)  # ok | info | warn | err
    m = Column(String, nullable=False)
    scpi = Column(String, nullable=False, default="")      # exact program message, when the step sent one
    response = Column(String, nullable=False, default="")  # readback / query response
    latency_ms = Column(Integer, nullable=False, default=0)
    # The reading this step produced, kept as numbers rather than only inside the
    # message text so a CSV export charts directly. Null means the step took no
    # reading — distinct from a reading of zero.
    voltage = Column(Float, nullable=True)
    current = Column(Float, nullable=True)
    power = Column(Float, nullable=True)
    # wall-clock of the step, so exported rows have a real time axis
    ts_ms = Column(Integer, nullable=True)
    # the channel this step ran against — a scenario may switch equipment part-way,
    # so the run's target list is not the answer for any single row
    unit = Column(String, nullable=False, default="")
