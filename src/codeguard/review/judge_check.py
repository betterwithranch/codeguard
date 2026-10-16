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
    confidence_threshold: float

    def check(self, files: Sequence[str]) -> list[Diagnostic]:
        matched = self.binding.files(files)
        if not matched:
            return []
        with ThreadPoolExecutor(max_workers=len(matched)) as executor:
            found = executor.map(self._diagnostics, matched)
            return [diagnostic for diagnostics in found for diagnostic in diagnostics]

    def _diagnostics(self, file: str) -> tuple[Diagnostic, ...]:
        verdict = self.judge.judge(JudgeRequest(self.binding.skill, file))
        return verdict.diagnostics_for(self.binding, file, self.confidence_threshold)
