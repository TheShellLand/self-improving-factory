"""Explicit, non-secret metadata and captured evaluation execution settings."""
import hashlib
import inspect

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.pi_runner import PiRunner


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
        return {
            "declared": self.model_dump(),
            "runner_source_sha256": hashlib.sha256(inspect.getsource(PiRunner).encode()).hexdigest(),
            "argv": config.argv(), "timeout": config.timeout,
            "cleanup_timeout": config.cleanup_timeout, "max_record_bytes": config.max_record_bytes,
            "max_events": config.max_events,
            "generation_settings": "pi defaults; not controlled by this adapter",
            "model_revision_verified": False,
        }
