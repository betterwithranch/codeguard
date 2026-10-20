from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from codeguard.config import RulesetLoader
from codeguard.judge_evals.judge_factory import JudgeFactory
from codeguard.judge_evals.rule_review import RuleReview
from codeguard.review import Bindings, JudgeError
from codeguard.rule_tests import JudgeEval, RuleTestResult


@dataclass(frozen=True)
class RulePackageReview:
    ruleset: RulesetLoader
    judges: JudgeFactory
    confidence_threshold: float

    def run(self) -> RuleTestResult:
        ruleset = self.ruleset.load()
        bindings = Bindings.from_rulesets([ruleset])
        if not bindings:
            return RuleTestResult()
        evaluated = {
            judge_eval.id
            for _, judge_eval in JudgeEval.in_ruleset(ruleset.root)
            if judge_eval.invalid
        }
        uncovered = [
            f"{binding.skill.name}: no eval with an invalid case"
            for binding in bindings
            if binding.skill.name not in evaluated
        ]
        gates = ruleset.qualified_gates()
        reviews = [RuleReview(binding, gates) for binding in bindings]
        with ThreadPoolExecutor(max_workers=len(reviews)) as executor:
            reviewed = list(executor.map(self._reviewed, reviews))
        return RuleTestResult.merge([RuleTestResult(problems=tuple(uncovered)), *reviewed])

    def _reviewed(self, review: RuleReview) -> RuleTestResult:
        try:
            problems = review.problems(self.judges, self.confidence_threshold)
        except JudgeError as error:
            rule = review.binding.skill.name
            return RuleTestResult(warnings=(f"{rule}: rule review not judged: {error}",))
        return RuleTestResult(problems=tuple(problems))
