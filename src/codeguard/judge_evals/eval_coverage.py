from dataclasses import dataclass

from codeguard.config import RulesetLoader
from codeguard.review import Bindings
from codeguard.rule_tests import Outcome, RuleTestResult, rule_evals


@dataclass(frozen=True)
class EvalCoverage:
    ruleset: RulesetLoader

    def run(self) -> RuleTestResult:
        ruleset = self.ruleset.load()
        evaluated = {
            dataset.name
            for _, dataset in rule_evals(ruleset.root)
            if any(
                case.expected_output and case.expected_output.outcome is Outcome.INVALID
                for case in dataset.cases
            )
        }
        return RuleTestResult(
            problems=tuple(
                f"{binding.skill.name}: no eval with an invalid case"
                for binding in Bindings.from_rulesets([ruleset])
                if binding.skill.name not in evaluated
            )
        )
