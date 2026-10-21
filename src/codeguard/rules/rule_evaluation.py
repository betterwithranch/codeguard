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
        # A repeat has to call the model again to show whether the verdict is stable.
        judge = rules.judges.cached if repeat == 1 else rules.judges.uncached
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
