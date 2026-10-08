from dataclasses import dataclass
from typing import TextIO

from codeguard.review.finding import Confidence, Finding

LOW_CONFIDENCE_HEADING = "Low confidence:"


@dataclass(frozen=True)
class Review:
    findings: tuple[Finding, ...]

    @property
    def blocks(self) -> bool:
        return any(finding.blocks for finding in self.findings)

    def write(self, out: TextIO) -> None:
        for finding in self._with_confidence(Confidence.HIGH):
            print(finding, file=out)
        low = self._with_confidence(Confidence.LOW)
        if low:
            print(LOW_CONFIDENCE_HEADING, file=out)
        for finding in low:
            print(finding, file=out)

    def _with_confidence(self, confidence: Confidence) -> list[Finding]:
        return [finding for finding in self.findings if finding.confidence is confidence]
