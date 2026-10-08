from collections.abc import Sequence
from typing import Protocol

from codeguard.review.concern import Concern
from codeguard.review.finding import Finding


class Judge(Protocol):
    def judge(self, concerns: Sequence[Concern]) -> list[Finding]: ...
