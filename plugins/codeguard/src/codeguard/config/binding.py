from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePath

from codeguard.review import Concern, Skill


@dataclass(frozen=True)
class Binding:
    skill: Skill
    paths: tuple[str, ...]

    def concern(self, files: Sequence[str]) -> Concern | None:
        selected = tuple(file for file in files if self._matches(file))
        return Concern(skill=self.skill, files=selected) if selected else None

    def _matches(self, file: str) -> bool:
        return any(PurePath(file).full_match(pattern) for pattern in self.paths)
