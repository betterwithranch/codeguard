from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
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
        if not self.checks:
            return diagnostics
        unblocked = _unblocked(files, diagnostics)
        with ThreadPoolExecutor(max_workers=len(self.checks)) as executor:
            found = executor.map(lambda check: check.check(unblocked), self.checks)
            return (*diagnostics, *(diagnostic for found_by in found for diagnostic in found_by))


def _unblocked(files: Sequence[str], diagnostics: Sequence[Diagnostic]) -> list[str]:
    blocked = {diagnostic.file for diagnostic in diagnostics if diagnostic.blocks}
    return [file for file in files if file not in blocked]
