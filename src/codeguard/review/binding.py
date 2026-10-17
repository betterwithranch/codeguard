from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import PurePath
from typing import Self

from codeguard.config import SKILL_FILE, BindingConfig, Ruleset, Skip
from codeguard.review.diagnostic import Severity
from codeguard.review.skill import Skill


@dataclass(frozen=True)
class Binding:
    rule: str
    skill: Skill
    paths: tuple[str, ...]
    severity: Severity
    model: str
    disable_skips: frozenset[Skip] = frozenset()

    @classmethod
    def from_config(cls, rule: str, binding: BindingConfig) -> Self:
        return cls(
            rule=rule,
            skill=Skill.from_file(binding.skill.name, binding.skill / SKILL_FILE),
            paths=binding.paths,
            severity=Severity(binding.severity),
            model=binding.model,
            disable_skips=binding.disable_skips,
        )

    @property
    def skips(self) -> tuple[Skip, ...]:
        return tuple(skip for skip in Skip if skip not in self.disable_skips)

    def files(self, changed: Sequence[str]) -> list[str]:
        return [file for file in changed if self._matches(file)]

    def _matches(self, file: str) -> bool:
        return any(PurePath(file).full_match(pattern) for pattern in self.paths)


class Bindings(tuple[Binding, ...]):
    @classmethod
    def from_rulesets(cls, rulesets: Iterable[Ruleset]) -> Self:
        return cls(
            Binding.from_config(rule, binding)
            for ruleset in rulesets
            for rule, binding in ruleset.selected_bindings().items()
        )
