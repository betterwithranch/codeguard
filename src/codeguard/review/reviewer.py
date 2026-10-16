from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from codeguard.review.diagnostic import Diagnostic
from codeguard.review.review import Review


class Step(Protocol):
    def run(
        self, files: Sequence[str], diagnostics: tuple[Diagnostic, ...]
    ) -> tuple[Diagnostic, ...]: ...


@dataclass(frozen=True)
class Reviewer:
    steps: tuple[Step, ...]

    def run(self, files: Sequence[str]) -> Review:
        diagnostics: tuple[Diagnostic, ...] = ()
        for step in self.steps:
            diagnostics = step.run(files, diagnostics)
        return Review(diagnostics=diagnostics)
