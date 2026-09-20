from typing import Optional
from pydantic import BaseModel


class OutputRequest(BaseModel):
    on: bool


class SetpointRequest(BaseModel):
    voltage: Optional[float] = None
    currentLimit: Optional[float] = None


class ProfileRequest(BaseModel):
    profile: str


class ModeRequest(BaseModel):
    mode: str  # FIX | SAS


class SasCurveRequest(BaseModel):
    isc: float
    imp: float
    vmp: float
    voc: float


class StateSlotRequest(BaseModel):
    slot: int  # 0 | 1 — the instrument's two non-volatile state locations


class PresetRequest(BaseModel):
    name: str
    mode: str = "FIX"
    note: str = ""
    volt: float = 0.0
    curr: float = 0.0
    isc: float = 0.0
    imp: float = 0.0
    vmp: float = 0.0
    voc: float = 0.0


class PresetEnableRequest(BaseModel):
    enabled: bool


class ApplyPresetRequest(BaseModel):
    unit: str


class AckRequest(BaseModel):
    pass


class CreateRackRequest(BaseModel):
    id: str
    name: str = ""
    loc: str = ""
    cap: int = 4


class UpdateRackRequest(BaseModel):
    name: Optional[str] = None
    loc: Optional[str] = None
    cap: Optional[int] = None


class AssignRequest(BaseModel):
    slot: str
    unitName: str


class TerminalExecuteRequest(BaseModel):
    act: str
    value: Optional[float] = None
    label: str


class CreateUnitRequest(BaseModel):
    name: str
    rack: str = "A"
    slot: Optional[int] = None
    ipAddress: Optional[str] = None
    macAddress: Optional[str] = None
    scpiPort: int = 5025
    transport: str = "vxi11"
    channel: int = 1
    pollMs: int = 1000


class CreateInstrumentRequest(BaseModel):
    """Add one E4360 mainframe and a unit for each of its output channels.
    channels: "auto" asks the instrument (SYST:CHAN?); "1" or "2" configures
    exactly that many without asking."""
    name: str
    rack: str = "A"
    ipAddress: str
    macAddress: Optional[str] = None
    scpiPort: int = 5025
    transport: str = "auto"
    channels: str = "auto"
    pollMs: int = 1000


class NetworkRequest(BaseModel):
    ipAddress: Optional[str] = None
    macAddress: Optional[str] = None
    scpiPort: Optional[int] = None
    transport: Optional[str] = None
    channel: Optional[int] = None
