from collections.abc import Sequence
from dataclasses import dataclass, field

from codeguard.review import Concern, Finding


@dataclass(frozen=True)
class RecordingJudge:
    findings: tuple[Finding, ...] = ()
    received: list[Concern] = field(default_factory=list)

    def judge(self, concerns: Sequence[Concern]) -> list[Finding]:
        self.received.extend(concerns)
        return list(self.findings)
