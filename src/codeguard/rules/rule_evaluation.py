from dataclasses import dataclass

from codeguard.judge_evals import EvalCoverage, JudgeEvalResult, JudgeEvalRunner
from codeguard.rules.rules import Rules


@dataclass(frozen=True)
class RuleEvaluation:
    rules: Rules

    def run(self, repeat: int = 1) -> JudgeEvalResult:
        rules = self.rules
        root = rules.working_tree.root
        config = rules.config
        # An eval tests the rule, not the code, so each run calls the model: a cached
        # verdict says nothing about the rule as it is now.
        judge = rules.judges.uncached
        return JudgeEvalResult.merge(
            result
            for loader in rules.resolver.own_rulesets
            for result in (
                JudgeEvalRunner(
                    root,
                    loader,
                    judge,
                    config.confidence_threshold,
                    repeat,
                    config.judge,
                    rules.ast_grep,
                ).run(),
                JudgeEvalResult(checks=EvalCoverage(loader).run()),
            )
        )
