from collections.abc import Sequence
from dataclasses import dataclass

from codeguard.review.check import Check
from codeguard.review.finding import Finding


@dataclass(frozen=True)
class CheckStage:
    checks: tuple[Check, ...]

    def run(self, files: Sequence[str], findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
        return (*findings, *(finding for check in self.checks for finding in check.check(files)))
