from pydantic import BaseModel, ConfigDict, Field

from codeguard.config.bindings_config import BindingsConfig


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    confidence_threshold: float = Field(default=0.9, ge=0, le=1)
    bindings: BindingsConfig = BindingsConfig({})
