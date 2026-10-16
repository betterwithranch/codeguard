from dataclasses import dataclass
from typing import TextIO

from codeguard.review.diagnostic import Diagnostic


@dataclass(frozen=True)
class Review:
    diagnostics: tuple[Diagnostic, ...]

    @property
    def blocks(self) -> bool:
        return any(diagnostic.blocks for diagnostic in self.diagnostics)

    def write(self, out: TextIO) -> None:
        for diagnostic in self.diagnostics:
            print(diagnostic, file=out)
