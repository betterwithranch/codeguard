from dataclasses import dataclass, field

from codeguard.review import JudgeRequest, Verdict


@dataclass(frozen=True)
class RecordingJudge:
    verdict: Verdict = Verdict(violations=())
    identity: str = "recording"
    received: list[JudgeRequest] = field(default_factory=list)

    def judge(self, request: JudgeRequest) -> Verdict:
        self.received.append(request)
        return self.verdict
