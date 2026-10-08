from collections.abc import Sequence
from typing import Protocol

from codeguard.review.concern import Concern


class ConcernSelector(Protocol):
    def concerns(self, files: Sequence[str]) -> list[Concern]: ...
