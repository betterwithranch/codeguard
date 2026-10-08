from collections.abc import Iterable
from dataclasses import dataclass
from typing import Self, TextIO


@dataclass(frozen=True)
class RuleTestResult:
    failed: bool
    problems: tuple[str, ...] = ()

    @classmethod
    def merge(cls, results: Iterable[Self]) -> Self:
        collected = list(results)
        return cls(
            failed=any(result.failed for result in collected),
            problems=tuple(problem for result in collected for problem in result.problems),
        )

    @property
    def passed(self) -> bool:
        return not self.failed and not self.problems

    def write(self, out: TextIO) -> None:
        for problem in self.problems:
            print(problem, file=out)
