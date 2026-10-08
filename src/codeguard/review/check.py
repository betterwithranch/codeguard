from collections.abc import Sequence
from typing import Protocol

from codeguard.review.finding import Finding


class Check(Protocol):
    def check(self, files: Sequence[str]) -> list[Finding]: ...
