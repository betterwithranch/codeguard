from collections.abc import Sequence
from typing import Protocol

from codeguard.review.finding import Finding


class Stage(Protocol):
    def run(self, files: Sequence[str], findings: tuple[Finding, ...]) -> tuple[Finding, ...]: ...
