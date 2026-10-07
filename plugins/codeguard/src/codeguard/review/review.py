from collections.abc import Sequence
from dataclasses import dataclass
from typing import Self, TextIO

from codeguard.review.check import Check
from codeguard.review.finding import Finding, Severity


@dataclass(frozen=True)
class Review:
    findings: tuple[Finding, ...]

    @classmethod
    def run(cls, checks: Sequence[Check], files: Sequence[str]) -> Self:
        return cls(findings=tuple(finding for check in checks for finding in check.check(files)))

    @property
    def blocks(self) -> bool:
        return any(finding.severity is Severity.ERROR for finding in self.findings)

    def write(self, out: TextIO) -> None:
        for finding in self.findings:
            print(finding, file=out)
