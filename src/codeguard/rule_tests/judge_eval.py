from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from codeguard.config import JUDGE_EVAL_DIR, ConfigError

EVAL_FILE_GLOB = "*-eval.yml"


class Outcome(StrEnum):
    INVALID = "invalid"
    VALID = "valid"
    SKIPPED = "skipped"


class EditCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    file: str = "module.py"
    before: str | None = None
    after: str


@dataclass(frozen=True)
class NumberedCase:
    outcome: Outcome
    number: int
    edit: EditCase

    @property
    def name(self) -> str:
        return f"{self.outcome} case {self.number}"

    @property
    def directory(self) -> str:
        return f"{self.outcome}-{self.number}"


class JudgeEval(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    invalid: tuple[EditCase, ...] = ()
    valid: tuple[EditCase, ...] = ()
    skipped: tuple[EditCase, ...] = ()

    @classmethod
    def load(cls, file: Path) -> Self:
        try:
            return cls.model_validate(yaml.safe_load(file.read_text()))
        except ValidationError as error:
            raise ConfigError.invalid(file, error) from error

    @classmethod
    def in_ruleset(cls, ruleset: Path) -> list[tuple[Path, Self]]:
        files = sorted((ruleset / JUDGE_EVAL_DIR).glob(EVAL_FILE_GLOB))
        return [(file, cls.load(file)) for file in files]

    def cases(self, *outcomes: Outcome) -> list[NumberedCase]:
        edits = {
            Outcome.INVALID: self.invalid,
            Outcome.VALID: self.valid,
            Outcome.SKIPPED: self.skipped,
        }
        return [
            NumberedCase(outcome, number, edit)
            for outcome in outcomes or tuple(Outcome)
            for number, edit in enumerate(edits[outcome], start=1)
        ]
