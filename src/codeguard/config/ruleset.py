from dataclasses import dataclass, field
from pathlib import Path

from codeguard.config.binding_config import BindingConfig
from codeguard.config.bindings_config import BindingsConfig
from codeguard.config.ruleset_config import RulesetConfig

PATTERN_RULE_DIR = "rules/pattern"
PATTERN_TEST_DIR = "rule-tests/pattern"
JUDGE_EVAL_DIR = "rule-evals"
BINDINGS_DIR = "bindings"
SKILLS_DIR = "skills"


@dataclass(frozen=True)
class Ruleset:
    name: str | None
    root: Path
    bindings: BindingsConfig = BindingsConfig({})
    selection: RulesetConfig = field(default_factory=RulesetConfig)

    def qualified_rule_id(self, rule_id: str) -> str:
        return rule_id if self.name is None else f"{self.name}/{rule_id}"

    def judged_rule_ids(self) -> frozenset[str]:
        return frozenset(binding.skill.name for binding in self.bindings.root.values())

    def selected_bindings(self) -> dict[str, BindingConfig]:
        return {
            self.qualified_rule_id(binding.skill.name): self.selection.apply(
                binding.skill.name, binding
            )
            for binding in self.bindings.root.values()
            if not self.selection.excludes(binding.skill.name)
        }
