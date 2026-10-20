import json
from dataclasses import dataclass
from typing import Self, TextIO

from codeguard.review.diagnostic import Category, Diagnostic


@dataclass(frozen=True)
class Review:
    diagnostics: tuple[Diagnostic, ...]

    @property
    def blocks(self) -> bool:
        return any(diagnostic.blocks for diagnostic in self.diagnostics)

    def with_judge_errors_as_warnings(self) -> Self:
        return type(self)(
            diagnostics=tuple(
                diagnostic.as_warning()
                if diagnostic.category is Category.JUDGE_ERROR
                else diagnostic
                for diagnostic in self.diagnostics
            )
        )

    def write(self, out: TextIO) -> None:
        for diagnostic in self.diagnostics:
            out.write(f"{diagnostic}\n")

    def write_json(self, out: TextIO) -> None:
        json.dump({"diagnostics": [diagnostic.as_json() for diagnostic in self.diagnostics]}, out)
        out.write("\n")
