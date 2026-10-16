from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from codeguard.review.diagnostic import Diagnostic


class Check(Protocol):
    def check(self, files: Sequence[str]) -> list[Diagnostic]: ...


@dataclass(frozen=True)
class CheckStep:
    checks: tuple[Check, ...]

    def run(
        self, files: Sequence[str], diagnostics: tuple[Diagnostic, ...]
    ) -> tuple[Diagnostic, ...]:
        unblocked = _unblocked(files, diagnostics)
        found = (diagnostic for check in self.checks for diagnostic in check.check(unblocked))
        return (*diagnostics, *found)


def _unblocked(files: Sequence[str], diagnostics: Sequence[Diagnostic]) -> list[str]:
    blocked = {diagnostic.file for diagnostic in diagnostics if diagnostic.blocks}
    return [file for file in files if file not in blocked]
