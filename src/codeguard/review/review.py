from dataclasses import dataclass
from typing import TextIO

from codeguard.review.diagnostic import Confidence, Diagnostic

_LOW_CONFIDENCE_HEADING = "Low confidence:"


@dataclass(frozen=True)
class Review:
    diagnostics: tuple[Diagnostic, ...]

    @property
    def blocks(self) -> bool:
        return any(diagnostic.blocks for diagnostic in self.diagnostics)

    def write(self, out: TextIO) -> None:
        for diagnostic in self._with_confidence(Confidence.HIGH):
            print(diagnostic, file=out)
        if low := self._with_confidence(Confidence.LOW):
            print(_LOW_CONFIDENCE_HEADING, file=out)
            for diagnostic in low:
                print(diagnostic, file=out)

    def _with_confidence(self, confidence: Confidence) -> list[Diagnostic]:
        return [
            diagnostic for diagnostic in self.diagnostics if diagnostic.confidence is confidence
        ]
