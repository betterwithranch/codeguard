from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Protocol

from pydantic import BaseModel, ConfigDict, Field

from codeguard.review.binding import Binding
from codeguard.review.diagnostic import Category, Diagnostic, ErrorType, Severity
from codeguard.review.skill import Skill

INSTRUCTIONS = (Path(__file__).parent / "judge.md").read_text()


@dataclass(frozen=True)
class JudgeRequest:
    skill: Skill
    file: str

    def instructions(self, content: str) -> str:
        numbered = "".join(
            f"{number:>6}\t{line}\n" for number, line in enumerate(content.splitlines(), start=1)
        )
        return f'{INSTRUCTIONS}\n<file path="{self.file}">\n{numbered}</file>\n'

    @property
    def prompt(self) -> str:
        return self.skill.text


class Violation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    file: str
    line: int
    message: str
    note: str
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
                note=violation.note,
                category=Category.JUDGED,
                confidence=violation.confidence,
            )
            for violation in self.violations
            if violation.file == file
        )


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

    def judge(self, request: JudgeRequest) -> Verdict: ...
