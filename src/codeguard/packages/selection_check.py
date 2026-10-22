from dataclasses import dataclass

from codeguard.config import Ruleset


@dataclass(frozen=True)
class SelectionCheck:
    ruleset: Ruleset

    def problems(self) -> list[str]:
        known = self.ruleset.pattern_rule_ids() | self.ruleset.judged_rule_ids()
        return [
            f"unknown rule {rule}" for rule in self.ruleset.selection.rule_ids if rule not in known
        ]
