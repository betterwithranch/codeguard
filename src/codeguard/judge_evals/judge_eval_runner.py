import asyncio
import tempfile
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext
from pydantic_evals.reporting import EvaluationReport

from codeguard.ast_grep import AstGrep
from codeguard.config import ChangeKind, RulesetLoader
from codeguard.judge_evals.judge_case import JudgeCase
from codeguard.judge_evals.judge_factory import JudgeFactory
from codeguard.review import Binding, Bindings, JudgeRequest, Verdict
from codeguard.rule_tests import JudgeEval, NumberedCase, Outcome, RuleTestResult
from codeguard.syntax import SyntaxScanner


@dataclass(frozen=True)
class _EditInputs:
    binding: Binding
    case: JudgeCase
    directory: Path

    def problem(
        self, verdict: Verdict, confidence_threshold: float, scanner: SyntaxScanner
    ) -> str | None:
        return self.case.problem(verdict, confidence_threshold) or self._trigger_problem(
            verdict, confidence_threshold, scanner
        )

    def _trigger_problem(
        self, verdict: Verdict, confidence_threshold: float, scanner: SyntaxScanner
    ) -> str | None:
        if not self.case.violates or ChangeKind.ANY in self.binding.triggers:
            return None
        lines = self.case.violation_lines(verdict, confidence_threshold)
        parsed = scanner.scan_files(self.directory, [self.case.file]).get(self.case.file)
        if not lines or parsed is None:
            return None
        kinds = [parsed.kinds_on(line) for line in lines]
        if any(not self.binding.triggers.isdisjoint(found) for found in kinds):
            return None
        on_lines = sorted({kind for found in kinds for kind in found})
        return (
            f"violation on line {', '.join(map(str, lines))} is outside the triggers "
            f"{', '.join(sorted(self.binding.triggers))}\n"
            f"  Add one of the kinds on that line to triggers in its binding: {', '.join(on_lines)}"
        )


@dataclass
class _MatchesOutcome(Evaluator[_EditInputs, Verdict, None]):
    confidence_threshold: float
    scanner: SyntaxScanner

    def evaluate(self, ctx: EvaluatorContext[_EditInputs, Verdict, None]) -> EvaluationReason:
        problem = ctx.inputs.problem(ctx.output, self.confidence_threshold, self.scanner)
        return EvaluationReason(value=problem is None, reason=problem)

    def build_serialization_arguments(self) -> dict[str, object]:
        # The scanner is a tool, not a setting worth recording with the run.
        return {"confidence_threshold": self.confidence_threshold}


@dataclass(frozen=True)
class JudgeEvalRunner:
    root: Path
    ruleset: RulesetLoader
    judges: JudgeFactory
    confidence_threshold: float
    repeat: int = 1
    concurrency: int | None = None
    ast_grep: AstGrep = AstGrep()

    def run(self) -> RuleTestResult:
        evals = JudgeEval.in_ruleset(self.ruleset.root)
        if not evals:
            return RuleTestResult()
        ruleset = self.ruleset.load()
        bindings = {binding.skill.name: binding for binding in Bindings.from_rulesets([ruleset])}
        scanner = SyntaxScanner.for_rulesets(self.ast_grep, [ruleset])
        problems: list[str] = []
        with ExitStack() as stack:
            cases: list[Case[_EditInputs, Verdict, None]] = []
            for file, judge_eval in evals:
                where = file.relative_to(self.root)
                binding = bindings.get(judge_eval.id)
                if binding is None:
                    problems.append(f"{where}: no judge rule {judge_eval.id}")
                    continue
                cases.extend(
                    _case(binding, case, f"{where} {case.name}", stack)
                    for case in judge_eval.cases(Outcome.INVALID, Outcome.VALID)
                )
            if cases:
                problems.extend(_problems(self._evaluate(cases, scanner)))
        return RuleTestResult(problems=tuple(problems))

    def _evaluate(
        self, cases: list[Case[_EditInputs, Verdict, None]], scanner: SyntaxScanner
    ) -> EvaluationReport[_EditInputs, Verdict, None]:
        dataset = Dataset[_EditInputs, Verdict, None](
            name="codeguard eval",
            cases=cases,
            evaluators=[_MatchesOutcome(self.confidence_threshold, scanner)],
        )
        return asyncio.run(
            dataset.evaluate(
                self._judge,
                task_name="judge",
                repeat=self.repeat,
                max_concurrency=self.concurrency,
                progress=False,
            )
        )

    def _judge(self, inputs: _EditInputs) -> Verdict:
        judge = self.judges(inputs.directory, inputs.binding.model)
        return judge.judge(JudgeRequest(inputs.binding.skill, inputs.case.file))


def _case(
    binding: Binding, case: NumberedCase, name: str, stack: ExitStack
) -> Case[_EditInputs, Verdict, None]:
    judged = JudgeCase(file=case.edit.file, violates=case.outcome == Outcome.INVALID)
    return Case(name=name, inputs=_EditInputs(binding, judged, _written(stack, case)))


def _problems(report: EvaluationReport[_EditInputs, Verdict, None]) -> list[str]:
    failed = [
        f"{case.name}: {case.inputs.binding.skill.name} {result.reason}"
        for case in report.cases
        for result in case.assertions.values()
        if not result.value
    ]
    not_evaluated = [
        f"{case.name}: {case.inputs.binding.skill.name} not evaluated: {failure.error_message}"
        for case in report.cases
        for failure in case.evaluator_failures
    ]
    not_judged = [
        f"{failure.name}: {failure.inputs.binding.skill.name} not judged: {failure.error_message}"
        for failure in report.failures
    ]
    return failed + not_evaluated + not_judged


def _written(stack: ExitStack, case: NumberedCase) -> Path:
    directory = Path(stack.enter_context(tempfile.TemporaryDirectory())) / case.directory
    file = directory / case.edit.file
    file.parent.mkdir(parents=True)
    file.write_text(case.edit.after)
    return directory
