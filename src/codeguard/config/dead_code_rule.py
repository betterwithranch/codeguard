from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from codeguard.config.config_error import ConfigError
from codeguard.config.severity import Severity


class DeadCodeRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    language: Literal["python"]
    severity: Severity
    whitelist: tuple[str, ...] = ()

    @classmethod
    def load_all(cls, rule_dir: Path) -> tuple[Self, ...]:
        return tuple(
            cls._load(path, document)
            for path in sorted(rule_dir.rglob("*.y*ml"))
            for document in yaml.safe_load_all(path.read_text())
            if document
        )

    @classmethod
    def _load(cls, path: Path, document: object) -> Self:
        try:
            return cls.model_validate(document)
        except ValidationError as error:
            raise ConfigError.invalid(path, error) from error
