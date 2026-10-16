from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from codeguard.config import ConfigError
from codeguard.judge_evals.judge_case import JudgeCase


class JudgeEval(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    valid: tuple[str, ...] = ()
    invalid: tuple[str, ...] = ()

    @classmethod
    def load(cls, file: Path) -> Self:
        try:
            return cls.model_validate(yaml.safe_load(file.read_text()))
        except ValidationError as error:
            raise ConfigError.invalid(file, error) from error

    def cases(self) -> tuple[JudgeCase, ...]:
        return (
            *(JudgeCase(file=file, violates=False) for file in self.valid),
            *(JudgeCase(file=file, violates=True) for file in self.invalid),
        )
