from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from codeguard.review.binding import Binding
from codeguard.review.diagnostic import Diagnostic
from codeguard.review.judge import Judge, JudgeRequest


@dataclass(frozen=True)
class JudgeCheck:
    binding: Binding
    judge: Judge

    def check(self, files: Sequence[str]) -> list[Diagnostic]:
        with ThreadPoolExecutor() as executor:
            found = executor.map(self._diagnostics, self.binding.files(files))
            return [diagnostic for diagnostics in found for diagnostic in diagnostics]

    def _diagnostics(self, file: str) -> tuple[Diagnostic, ...]:
        verdict = self.judge.judge(JudgeRequest(self.binding.skill, file))
        return verdict.diagnostics_for(self.binding, file)
