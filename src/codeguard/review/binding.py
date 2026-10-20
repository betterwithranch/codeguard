from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Self

from codeguard.config import (
    SKILL_FILE,
    BindingConfig,
    ChangeKind,
    PathScope,
    Ruleset,
    Severity,
    Skip,
)
from codeguard.review.skill import Skill
from codeguard.working_tree import AllLines, ChangedLines


@dataclass(frozen=True)
class Binding:
    rule: str
    skill: Skill
    paths: tuple[str, ...]
    severity: Severity
    model: str
    triggers: frozenset[str]
    disable_skips: frozenset[Skip] = frozenset()
    exclude_paths: tuple[str, ...] = ()

    @classmethod
    def from_config(cls, rule: str, binding: BindingConfig) -> Self:
        return cls(
            rule=rule,
            skill=Skill.from_file(binding.skill.name, binding.skill / SKILL_FILE),
            paths=binding.paths,
            severity=binding.severity,
            model=binding.model,
            triggers=binding.triggers,
            disable_skips=binding.disable_skips,
            exclude_paths=binding.exclude_paths,
        )

    @property
    def skips(self) -> tuple[Skip, ...]:
        return tuple(skip for skip in Skip if skip not in self.disable_skips)

    def files(self, changed: Sequence[str]) -> list[str]:
        return [file for file in changed if self._matches(file)]

    def is_triggered(self, scope: ChangedLines | AllLines, file: str) -> bool:
        kinds = scope.kinds_of(file)
        return (
            kinds is None or ChangeKind.ANY in self.triggers or not self.triggers.isdisjoint(kinds)
        )

    def _matches(self, file: str) -> bool:
        return PathScope(self.paths, self.exclude_paths).matches(file)


class Bindings(tuple[Binding, ...]):
    @classmethod
    def from_rulesets(cls, rulesets: Iterable[Ruleset]) -> Self:
        return cls(
            Binding.from_config(rule, binding)
            for ruleset in rulesets
            for rule, binding in ruleset.selected_bindings().items()
        )
