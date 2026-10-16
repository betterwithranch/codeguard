from collections.abc import Iterable
from dataclasses import dataclass
from typing import Self, TextIO


@dataclass(frozen=True)
class EvalResult:
    problems: tuple[str, ...] = ()

    @classmethod
    def merge(cls, results: Iterable[Self]) -> Self:
        return cls(problems=tuple(problem for result in results for problem in result.problems))

    @property
    def passed(self) -> bool:
        return not self.problems

    def write(self, out: TextIO) -> None:
        for problem in self.problems:
            out.write(f"{problem}\n")
