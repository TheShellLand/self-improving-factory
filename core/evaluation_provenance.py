"""Explicit, non-secret metadata and captured evaluation execution settings."""
import hashlib
import inspect
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.pi_runner import PiRunner


class EvaluationExecutionRecord(BaseModel):
    """Validate saved declarations without claiming independent verification."""
    model_config = ConfigDict(extra="forbid", strict=True)
    declared: "EvaluationProvenanceConfig"
    runner_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    argv: list[str] = Field(min_length=1)
    timeout: float = Field(gt=0, allow_inf_nan=False)
    cleanup_timeout: float = Field(gt=0, allow_inf_nan=False)
    max_record_bytes: int = Field(gt=0)
    max_events: int = Field(gt=0)
    generation_settings: Literal["pi defaults; not controlled by this adapter"]
    model_revision_verified: Literal[False]

    @field_validator("argv")
    @classmethod
    def valid_arguments(cls, value):
        if any(not argument.strip() or "\0" in argument for argument in value):
            raise ValueError("Invalid execution argument")
        return value


class EvaluationProvenanceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}([0-9a-f]{24})?$")
    pi_version: str = Field(min_length=1)
    model_revision: str | None = None

    @field_validator("pi_version", "model_revision")
    @classmethod
    def nonblank(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Version must not be blank")
        return value

    def capture(self, client):
        config = client.config
        if not config.model or not config.provider:
            raise ValueError("Evaluation requires explicit model and provider settings")
        record = {
            "declared": self.model_dump(),
            "runner_source_sha256": hashlib.sha256(inspect.getsource(PiRunner).encode()).hexdigest(),
            "argv": config.argv(), "timeout": config.timeout,
            "cleanup_timeout": config.cleanup_timeout, "max_record_bytes": config.max_record_bytes,
            "max_events": config.max_events,
            "generation_settings": "pi defaults; not controlled by this adapter",
            "model_revision_verified": False,
        }
        return EvaluationExecutionRecord.model_validate(record).model_dump()
