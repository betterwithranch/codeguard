from dataclasses import dataclass

from codeguard.config import Ruleset


@dataclass(frozen=True)
class SelectionCheck:
    ruleset: Ruleset

    def problems(self) -> list[str]:
        pattern_rules = self.ruleset.pattern_rule_ids()
        known = pattern_rules | self.ruleset.judged_rule_ids()
        selection = self.ruleset.selection
        unknown = [f"unknown rule {rule}" for rule in selection.rule_ids if rule not in known]
        model_on_pattern_rule = [
            f"rules.{rule}.model: a pattern rule has no model"
            for rule, override in selection.rules.items()
            if rule in pattern_rules and override.model is not None
        ]
        return [*unknown, *model_on_pattern_rule]
