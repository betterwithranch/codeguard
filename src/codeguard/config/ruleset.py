from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from codeguard.config.binding_config import BindingConfig
from codeguard.config.bindings_config import BindingsConfig
from codeguard.config.path_scope import PathScope
from codeguard.config.pattern_binding_config import PatternBindingsConfig
from codeguard.config.ruleset_config import RulesetConfig

PATTERN_RULE_DIR = "rules/pattern"
PATTERN_TEST_DIR = "rule-tests/pattern"
JUDGE_EVAL_DIR = "rule-evals"
BINDINGS_DIR = "bindings"
SKILLS_DIR = "skills"


class _PatternRule(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str


@dataclass(frozen=True)
class Ruleset:
    name: str | None
    root: Path
    bindings: BindingsConfig = BindingsConfig({})
    selection: RulesetConfig = field(default_factory=RulesetConfig)
    pattern_bindings: PatternBindingsConfig = PatternBindingsConfig({})

    def qualified_rule_id(self, rule_id: str) -> str:
        return rule_id if self.name is None else f"{self.name}/{rule_id}"

    def judged_rule_ids(self) -> frozenset[str]:
        return frozenset(binding.skill.name for binding in self.bindings.root.values())

    def pattern_rule_ids(self) -> frozenset[str]:
        rule_dir = self.root / PATTERN_RULE_DIR
        return frozenset(
            _PatternRule.model_validate(document).id
            for path in sorted(rule_dir.rglob("*.y*ml"))
            for document in yaml.safe_load_all(path.read_text())
            if document
        )

    def selected_bindings(self) -> dict[str, BindingConfig]:
        return {
            self.qualified_rule_id(binding.skill.name): self.selection.apply(
                binding.skill.name, binding
            )
            for binding in self.bindings.root.values()
            if not self.selection.excludes(binding.skill.name)
        }

    def pattern_scope(self, rule: str) -> PathScope:
        return self.selection.apply_scope(rule, self.pattern_bindings.scope(rule))
