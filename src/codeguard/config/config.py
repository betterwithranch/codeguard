from pydantic import BaseModel, ConfigDict

from codeguard.config.bindings_config import BindingsConfig


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bindings: BindingsConfig = BindingsConfig({})
