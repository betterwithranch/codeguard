from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic_evals import Dataset

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


type RuleEval = Dataset[EditCase, EditReview, None]


def rule_evals(ruleset: Path) -> list[tuple[Path, RuleEval]]:
    directory = ruleset / JUDGE_EVAL_DIR
    misnamed = sorted(directory.glob(_MISNAMED_GLOB))
    if misnamed:
        raise ConfigError(
            "rule evals are <rule id>.yaml datasets; rename or convert:"
            + "".join(f"\n  {file}" for file in misnamed)
        )
    return [_load(file) for file in sorted(directory.glob(EVAL_FILE_GLOB))]


def _load(file: Path) -> tuple[Path, RuleEval]:
    try:
        dataset = Dataset[EditCase, EditReview, None].from_text(
            file.read_text(), default_name=file.stem
        )
    except ValidationError as error:
        raise ConfigError.invalid(file, error) from error
    except (ValueError, ExceptionGroup) as error:
        raise ConfigError(f"{file} is invalid:\n  {error}") from error
    problems = [
        f"{case.name or f'case {number}'} has no {field}"
        for number, case in enumerate(dataset.cases, start=1)
        for field, value in (("name", case.name), ("expected_output", case.expected_output))
        if value is None
    ]
    if problems:
        raise ConfigError(f"{file} is invalid:" + "".join(f"\n  {problem}" for problem in problems))
    return file, dataset
