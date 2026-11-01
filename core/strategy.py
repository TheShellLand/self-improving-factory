"""Structural validation for reflection proposals, not quality evaluation."""
import json

from pydantic import BaseModel, ConfigDict, JsonValue, field_validator


class StrategyProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    logic_description: str
    prompt_weights: dict[str, JsonValue]

    @field_validator("logic_description")
    @classmethod
    def nonblank_description(cls, value):
        if not value.strip():
            raise ValueError("A nonempty explanation is required")
        return value

    @field_validator("prompt_weights", mode="before")
    @classmethod
    def parse_weights(cls, value):
        if isinstance(value, str):
            value = json.loads(value, object_pairs_hook=cls.unique_object)
        return value

    @field_validator("prompt_weights")
    @classmethod
    def finite_weights(cls, value):
        json.dumps(value, allow_nan=False)
        return value

    @staticmethod
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate strategy key")
            result[key] = value
        return result
