import time
from dataclasses import dataclass, field

from codeguard.review.judge import JudgeError


@dataclass(frozen=True)
class Deadline:
    minutes: int
    started: float = field(default_factory=time.monotonic)

    def remaining_seconds(self) -> float:
        return self.started + self.minutes * 60 - time.monotonic()

    def reached(self) -> JudgeError:
        return JudgeError(f"The review reached its {self.minutes}-minute time limit.")
