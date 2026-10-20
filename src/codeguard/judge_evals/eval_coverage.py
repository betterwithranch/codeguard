from dataclasses import dataclass

from codeguard.config import RulesetLoader
from codeguard.review import Bindings
from codeguard.rule_tests import JudgeEval, RuleTestResult


@dataclass(frozen=True)
class EvalCoverage:
    ruleset: RulesetLoader

    def run(self) -> RuleTestResult:
        ruleset = self.ruleset.load()
        evaluated = {
            judge_eval.id
            for _, judge_eval in JudgeEval.in_ruleset(ruleset.root)
            if judge_eval.invalid
        }
        return RuleTestResult(
            problems=tuple(
                f"{binding.skill.name}: no eval with an invalid case"
                for binding in Bindings.from_rulesets([ruleset])
                if binding.skill.name not in evaluated
            )
        )
