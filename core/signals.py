"""The internal signal contract, independent of the agent's wire protocol."""
import json
import time
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Viewport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: int = Field(default=1920, gt=0, strict=True)
    height: int = Field(default=1080, gt=0, strict=True)


class SignalPulse(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)
    signal_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: float = Field(default_factory=time.time, ge=0, allow_inf_nan=False)
    source_agent: str = Field(default="orchestrator", min_length=1)
    action_type: Literal["INPUT", "ACTION_START", "OBSERVATION", "RESULT", "REFLECTION"] = "INPUT"
    payload: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
    viewport: Viewport = Field(default_factory=Viewport)
    visual_state: dict | None = None

    @field_validator("signal_id")
    @classmethod
    def valid_id(cls, value):
        return str(UUID(value))

    def to_json(self):
        return json.dumps(self.model_dump(), allow_nan=False)
