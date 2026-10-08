from collections.abc import Sequence
from dataclasses import dataclass

from codeguard.review.finding import Finding
from codeguard.review.review import Review
from codeguard.review.stage import Stage


@dataclass(frozen=True)
class Reviewer:
    stages: tuple[Stage, ...]

    def run(self, files: Sequence[str]) -> Review:
        findings: tuple[Finding, ...] = ()
        for stage in self.stages:
            findings = stage.run(files, findings)
        return Review(findings=findings)
