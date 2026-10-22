from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field

from codeguard.review.binding import Binding
from codeguard.review.diagnostic import Category, Diagnostic, ErrorType, Severity
from codeguard.review.skill import Skill
from codeguard.working_tree import AllLines, ChangedLines

INSTRUCTIONS = (Path(__file__).parent / "judge.md").read_text()


@dataclass(frozen=True)
class JudgeRequest:
    skill: Skill
    file: str
    changes: str

    @classmethod
    def of_change(cls, skill: Skill, root: Path, file: str, scope: ChangedLines | AllLines) -> Self:
        raw = (root / file).read_bytes().splitlines()
        content = [line.decode(errors="replace") for line in raw]
        lines = scope.judged_lines(file)
        shown = range(1, len(content) + 1) if lines is None else sorted(lines)
        changed = scope.changed_points(file)
        changes = "".join(
            f"{'+' if changed is None or number in changed else ' '}{number:>6}\t"
            f"{content[number - 1]}\n"
            for number in shown
            if number <= len(content)
        )
        return cls(skill, file, changes)

    @property
    def instructions(self) -> str:
        return f'{INSTRUCTIONS}\n<changes path="{self.file}">\n{self.changes}</changes>\n'

    @property
    def prompt(self) -> str:
        return self.skill.text


class Violation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    file: str
    line: int
    message: str
    confidence: float = Field(ge=0, le=1)

    def severity(self, severity: Severity, threshold: float) -> Severity:
        if severity is Severity.ERROR and self.confidence < threshold:
            return Severity.WARNING
        return severity


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    violations: tuple[Violation, ...]

    def diagnostics_for(
        self, binding: Binding, file: str, threshold: float
    ) -> tuple[Diagnostic, ...]:
        return tuple(
            Diagnostic(
                rule=binding.rule,
                file=violation.file,
                line=violation.line,
                message=violation.message,
                severity=violation.severity(binding.severity, threshold),
                note=None,
                category=Category.JUDGED,
                confidence=violation.confidence,
            )
            for violation in self.violations
            if violation.file == file
        )


@dataclass(frozen=True)
class Judgement:
    verdict: Verdict
    loaded_files: tuple[str, ...] = ()


class JudgeError(Exception):
    error_type: ClassVar[ErrorType]


class JudgeTimeout(JudgeError):
    error_type = ErrorType.TIMEOUT


class JudgeProcessError(JudgeError):
    error_type = ErrorType.PROCESS


class JudgeNoVerdict(JudgeError):
    error_type = ErrorType.NO_VERDICT


class Judge(Protocol):
    @property
    def identity(self) -> str: ...

    def judge(self, request: JudgeRequest) -> Judgement: ...
