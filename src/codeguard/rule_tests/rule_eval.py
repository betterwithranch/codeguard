from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from codeguard.config import JUDGE_EVAL_DIR, ConfigError

EVAL_FILE_GLOB = "*.yaml"
_MISNAMED_GLOB = "*.yml"


class Outcome(StrEnum):
    INVALID = "invalid"
    UNCERTAIN = "uncertain"
    VALID = "valid"
    SKIPPED = "skipped"


class EditCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    file: str = "module.py"
    before: str | None = None
    after: str
    unchanged: dict[str, str] = {}

    @model_validator(mode="after")
    def paths_are_inside_the_repository(self) -> Self:
        for path in (self.file, *self.unchanged):
            posix = PurePosixPath(path)
            if posix.is_absolute() or ".." in posix.parts or str(posix) != path:
                raise ValueError(f"{path} is not a normalized relative path")
        return self

    @model_validator(mode="after")
    def file_is_not_unchanged(self) -> Self:
        if self.file in self.unchanged:
            raise ValueError(f"unchanged lists the edited file {self.file}")
        return self

    def edits(self, prefix: str = "") -> dict[str, "EditCase"]:
        unchanged = {
            f"{prefix}{path}": EditCase(file=path, before=text, after=text)
            for path, text in self.unchanged.items()
        }
        return {**unchanged, f"{prefix}{self.file}": self}


class JudgedViolation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    line: int
    confidence: float
    message: str
    kinds: tuple[str, ...] | None = None


class EditReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: Outcome
    violations: tuple[JudgedViolation, ...] = ()

    @property
    def listing(self) -> str:
        return "".join(
            f"\n  line {violation.line} ({violation.confidence:.2f}): {violation.message}"
            for violation in self.violations
        )


class RuleEvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    inputs: EditCase
    expected_output: EditReview


class RuleEval(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    cases: tuple[RuleEvalCase, ...]

    @field_validator("cases")
    @classmethod
    def names_are_unique(cls, cases: tuple[RuleEvalCase, ...]) -> tuple[RuleEvalCase, ...]:
        names = [case.name for case in cases]
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise ValueError(f"cases share a name: {', '.join(repeated)}")
        return cases


def rule_evals(ruleset: Path) -> list[tuple[Path, RuleEval]]:
    directory = ruleset / JUDGE_EVAL_DIR
    misnamed = sorted(directory.glob(_MISNAMED_GLOB))
    if misnamed:
        raise ConfigError(
            "rule evals are <rule id>.yaml files; rename or convert:"
            + "".join(f"\n  {file}" for file in misnamed)
        )
    return [_load(file) for file in sorted(directory.glob(EVAL_FILE_GLOB))]


def _load(file: Path) -> tuple[Path, RuleEval]:
    try:
        data = yaml.safe_load(file.read_text())
    except yaml.YAMLError as error:
        raise ConfigError(f"{file} is invalid:\n  {error}") from error
    if isinstance(data, dict):
        data = {"name": file.stem, **data}
    try:
        return file, RuleEval.model_validate(data)
    except ValidationError as error:
        raise ConfigError.invalid(file, error) from error
