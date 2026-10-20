from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from codeguard.config import ConfigError

TRIGGER_TEST_GLOB = "*-test.yml"


class TriggerCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    file: str = "module.py"
    before: str | None = None
    after: str


class TriggerTest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    triggered: tuple[TriggerCase, ...] = ()
    skipped: tuple[TriggerCase, ...] = ()

    @classmethod
    def load(cls, file: Path) -> Self:
        try:
            return cls.model_validate(yaml.safe_load(file.read_text()))
        except ValidationError as error:
            raise ConfigError.invalid(file, error) from error
