from dataclasses import dataclass

from codeguard.config import Ruleset


@dataclass(frozen=True)
class SelectionCheck:
    ruleset: Ruleset

    def problems(self) -> list[str]:
        unjudged = {
            **dict.fromkeys(self.ruleset.pattern_rule_ids(), "pattern"),
            **dict.fromkeys(self.ruleset.dead_code_rule_ids(), "dead-code"),
        }
        known = unjudged.keys() | self.ruleset.judged_rule_ids()
        selection = self.ruleset.selection
        unknown = [f"unknown rule {rule}" for rule in selection.rule_ids if rule not in known]
        model_on_unjudged_rule = [
            f"rules.{rule}.model: a {unjudged[rule]} rule has no model"
            for rule, override in selection.rules.items()
            if rule in unjudged and override.model is not None
        ]
        return [*unknown, *model_on_unjudged_rule]
