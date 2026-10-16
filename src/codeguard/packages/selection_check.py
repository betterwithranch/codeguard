from dataclasses import dataclass

import yaml
from pydantic import BaseModel, ConfigDict

from codeguard.config import PATTERN_RULE_DIR, Ruleset


class PatternRule(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    id: str


@dataclass(frozen=True)
class SelectionCheck:
    ruleset: Ruleset

    def problems(self) -> list[str]:
        pattern_rules = self._pattern_rule_ids()
        known = pattern_rules | self.ruleset.judged_rule_ids()
        selection = self.ruleset.selection
        unknown = [f"unknown rule {rule}" for rule in selection.rule_ids if rule not in known]
        model_on_pattern_rule = [
            f"rules.{rule}.model: a pattern rule has no model"
            for rule, override in selection.rules.items()
            if rule in pattern_rules and override.model is not None
        ]
        return [*unknown, *model_on_pattern_rule]

    def _pattern_rule_ids(self) -> frozenset[str]:
        rule_dir = self.ruleset.root / PATTERN_RULE_DIR
        return frozenset(
            PatternRule.model_validate(document).id
            for path in sorted(rule_dir.rglob("*.y*ml"))
            for document in yaml.safe_load_all(path.read_text())
            if document
        )
