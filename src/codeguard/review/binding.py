import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Self

from codeguard.config import (
    SKILL_FILE,
    BindingConfig,
    ChangeKind,
    JudgeModel,
    PathScope,
    Ruleset,
    Severity,
)
from codeguard.review.skill import Skill
from codeguard.working_tree import AllLines, ChangedLines


@dataclass(frozen=True)
class Binding:
    rule: str
    skill: Skill
    paths: tuple[str, ...]
    severity: Severity
    model: JudgeModel
    triggers: frozenset[str]
    exclude_paths: tuple[str, ...] = ()

    @classmethod
    def from_config(cls, rule: str, binding: BindingConfig) -> Self:
        return cls(
            rule=rule,
            skill=Skill.from_file(binding.skill.name, binding.skill / SKILL_FILE),
            paths=binding.paths,
            severity=binding.severity,
            model=binding.judge_model,
            triggers=binding.triggers,
            exclude_paths=binding.exclude_paths,
        )

    @property
    def version(self) -> str:
        """Identify what decides the rule's verdicts, other than its model."""
        rule = [self.skill.text, sorted(self.triggers), self.paths, self.exclude_paths]
        return hashlib.sha256(json.dumps(rule).encode()).hexdigest()[:12]

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
