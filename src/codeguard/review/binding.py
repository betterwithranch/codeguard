from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import PurePath
from typing import Self

from codeguard.config import SKILL_FILE, BindingConfig, BindingsConfig
from codeguard.review.diagnostic import Severity
from codeguard.review.skill import Skill


@dataclass(frozen=True)
class Binding:
    skill: Skill
    paths: tuple[str, ...]
    severity: Severity

    @classmethod
    def from_config(cls, binding: BindingConfig) -> Self:
        return cls(
            skill=Skill.from_file(binding.skill.name, binding.skill / SKILL_FILE),
            paths=binding.paths,
            severity=Severity(binding.severity),
        )

    def files(self, changed: Sequence[str]) -> list[str]:
        return [file for file in changed if self._matches(file)]

    def _matches(self, file: str) -> bool:
        return any(PurePath(file).full_match(pattern) for pattern in self.paths)


class Bindings(tuple[Binding, ...]):
    @classmethod
    def from_config(cls, bindings: BindingsConfig) -> Self:
        return cls(Binding.from_config(binding) for binding in bindings.root.values())
