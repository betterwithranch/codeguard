from pathlib import Path
from typing import Protocol

from codeguard.review import Judge


class JudgeFactory(Protocol):
    def __call__(self, root: Path, model: str) -> Judge: ...
