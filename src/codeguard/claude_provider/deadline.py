import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Deadline:
    minutes: int
    started: float = field(default_factory=time.monotonic)

    def remaining_seconds(self) -> float:
        return self.started + self.minutes * 60 - time.monotonic()
