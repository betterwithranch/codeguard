from collections.abc import Sequence
from dataclasses import dataclass

from codeguard.review.concern_selector import ConcernSelector
from codeguard.review.finding import Finding
from codeguard.review.judge import Judge


@dataclass(frozen=True)
class JudgeStage:
    judge: Judge
    selector: ConcernSelector

    def run(self, files: Sequence[str], findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
        failed = {finding.file for finding in findings if finding.blocks}
        passing = [file for file in files if file not in failed]
        return (*findings, *self.judge.judge(self.selector.concerns(passing)))
