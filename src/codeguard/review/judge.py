from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from codeguard.review.binding import Binding
from codeguard.review.diagnostic import Confidence, Diagnostic
from codeguard.review.skill import Skill

INSTRUCTIONS = (Path(__file__).parent / "judge.md").read_text()


@dataclass(frozen=True)
class JudgeRequest:
    skill: Skill
    file: str

    @property
    def instructions(self) -> str:
        return INSTRUCTIONS

    @property
    def prompt(self) -> str:
        return f"{self.skill.text.rstrip()}\n\n{self.file}\n"


class Violation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    file: str
    line: int
    message: str
    note: str
    confidence: Confidence


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    violations: tuple[Violation, ...]

    def diagnostics_for(self, binding: Binding, file: str) -> tuple[Diagnostic, ...]:
        return tuple(
            Diagnostic(
                rule=binding.skill.name,
                file=violation.file,
                line=violation.line,
                message=violation.message,
                severity=binding.severity,
                note=violation.note,
                confidence=violation.confidence,
            )
            for violation in self.violations
            if violation.file == file
        )


class Judge(Protocol):
    @property
    def identity(self) -> str: ...

    def judge(self, request: JudgeRequest) -> Verdict: ...
