import asyncio
from dataclasses import dataclass
from pathlib import Path

from pydantic_evals import Case, Dataset

from codeguard.ast_grep import AstGrep
from codeguard.config import JudgeConfig, RulesetLoader
from codeguard.judge_evals.edit_evaluators import PartialEqualsExpected, ViolationsOnTriggers
from codeguard.judge_evals.edit_review_task import EditReviewTask
from codeguard.judge_evals.installed_evals import check_installed_evals
from codeguard.judge_evals.judge_eval_result import JudgeEvalResult, RuleEvalReport
from codeguard.judge_evals.judge_factory import JudgeFactory
from codeguard.review import Binding, Bindings
from codeguard.rule_tests import EditCase, EditReview, RuleEval, RuleTestResult, rule_evals
from codeguard.syntax import SyntaxScanner


@dataclass(frozen=True)
class JudgeEvalRunner:
    root: Path
    ruleset: RulesetLoader
    judges: JudgeFactory
    confidence_threshold: float
    repeat: int = 1
    judge_config: JudgeConfig = JudgeConfig()
    ast_grep: AstGrep = AstGrep()

    def run(self) -> JudgeEvalResult:
        evals = rule_evals(self.ruleset.root)
        if not evals:
            return JudgeEvalResult()
        check_installed_evals()
        ruleset = self.ruleset.load()
        bindings = {binding.skill.name: binding for binding in Bindings.from_rulesets([ruleset])}
        unknown = tuple(
            f"{file.relative_to(self.root)}: no judge rule {dataset.name}"
            for file, dataset in evals
            if dataset.name not in bindings
        )
        experiments = [
            (dataset, bindings[dataset.name]) for _, dataset in evals if dataset.name in bindings
        ]
        scanner = SyntaxScanner.for_rulesets(self.ast_grep, [ruleset])
        reports = asyncio.run(self._evaluate_all(experiments, scanner))
        return JudgeEvalResult(reports=tuple(reports), checks=RuleTestResult(problems=unknown))

    async def _evaluate_all(
        self, experiments: list[tuple[RuleEval, Binding]], scanner: SyntaxScanner
    ) -> list[RuleEvalReport]:
        return await asyncio.gather(
            *(self._evaluate(dataset, binding, scanner) for dataset, binding in experiments)
        )

    async def _evaluate(
        self, rule_eval: RuleEval, binding: Binding, scanner: SyntaxScanner
    ) -> RuleEvalReport:
        dataset = Dataset[EditCase, EditReview, None](
            name=rule_eval.name,
            cases=[
                Case(name=case.name, inputs=case.inputs, expected_output=case.expected_output)
                for case in rule_eval.cases
            ],
            evaluators=[
                PartialEqualsExpected(),
                ViolationsOnTriggers(tuple(sorted(binding.triggers)), self.confidence_threshold),
            ],
        )
        model = binding.model
        task = EditReviewTask(binding, self.judges, self.confidence_threshold, scanner)
        return await dataset.evaluate(
            task,
            name=f"{dataset.name} on {model.name}",
            task_name=model.name,
            metadata={
                "provider": model.provider,
                "model": model.name,
                "confidence_threshold": self.confidence_threshold,
            },
            repeat=self.repeat,
            max_concurrency=self.judge_config.concurrency(model.provider),
            progress=False,
        )
