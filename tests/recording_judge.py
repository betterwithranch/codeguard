from dataclasses import dataclass, field
from pathlib import Path

from codeguard.review import JudgeError, JudgeRequest, Verdict


@dataclass(frozen=True)
class RecordingJudge:
    verdict: Verdict = Verdict(violations=())
    identity: str = "recording"
    received: list[JudgeRequest] = field(default_factory=list)

    def judge(self, request: JudgeRequest) -> Verdict:
        self.received.append(request)
        return self.verdict


@dataclass(frozen=True)
class FailingJudge:
    error: str = "gemini failed with 502: upstream request failed"
    identity: str = "failing"

    def judge(self, request: JudgeRequest) -> Verdict:
        raise JudgeError(self.error)


@dataclass(frozen=True)
class JudgeCreation:
    root: Path
    model: str


@dataclass(frozen=True)
class RecordingJudges:
    judge: RecordingJudge | FailingJudge
    created: list[JudgeCreation] = field(default_factory=list)

    def __call__(self, root: Path, model: str) -> RecordingJudge | FailingJudge:
        self.created.append(JudgeCreation(root, model))
        return self.judge
