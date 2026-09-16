from typing import Optional
from pydantic import BaseModel


class OutputRequest(BaseModel):
    on: bool


class SetpointRequest(BaseModel):
    voltage: Optional[float] = None
    currentLimit: Optional[float] = None


class ProfileRequest(BaseModel):
    profile: str


class AckRequest(BaseModel):
    pass


class AssignRequest(BaseModel):
    slot: str
    unitName: str


class TerminalExecuteRequest(BaseModel):
    act: str
    value: Optional[float] = None
    label: str
