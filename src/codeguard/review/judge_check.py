from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from codeguard.review.binding import Binding
from codeguard.review.diagnostic import Diagnostic, Severity
from codeguard.review.judge import Judge, JudgeError, JudgeRequest


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
        try:
            verdict = self.judge.judge(JudgeRequest(self.binding.skill, file))
        except JudgeError as error:
            return (
                Diagnostic(
                    rule=self.binding.rule,
                    file=file,
                    line=None,
                    message="The judge call failed, so this rule was not checked.",
                    severity=Severity.ERROR,
                    note=str(error),
                ),
            )
        return verdict.diagnostics_for(self.binding, file, self.confidence_threshold)
