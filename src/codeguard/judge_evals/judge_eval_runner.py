from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from codeguard.ast_grep import AstGrep
from codeguard.config import ChangeKind, Ruleset, RulesetLoader
from codeguard.judge_evals.judge_case import JudgeCase
from codeguard.judge_evals.judge_factory import JudgeFactory
from codeguard.review import Binding, Bindings, JudgeError, JudgeRequest, Verdict
from codeguard.rule_tests import EditRepo, JudgeEval, NumberedCase, Outcome, RuleTestResult
from codeguard.syntax import SyntaxScanner


@dataclass(frozen=True)
class _CaseRun:
    binding: Binding
    case: JudgeCase
    name: str
    directory: Path
    lines: frozenset[int] | None
    judges: JudgeFactory
    run: int
    scanner: SyntaxScanner

    def problem(self, confidence_threshold: float) -> str | None:
        judge = self.judges(self.directory, self.binding.model)
        request = JudgeRequest.of_change(
            self.binding.skill, self.directory, self.case.file, self.lines
        )
        verdict = judge.judge(request).verdict
        return self.case.problem(verdict, confidence_threshold) or self._trigger_problem(
            verdict, confidence_threshold
        )

    def _trigger_problem(self, verdict: Verdict, confidence_threshold: float) -> str | None:
        if not self.case.violates or ChangeKind.ANY in self.binding.triggers:
            return None
        lines = self.case.violation_lines(verdict, confidence_threshold)
        parsed = self.scanner.scan_files(self.directory, [self.case.file]).get(self.case.file)
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


@dataclass(frozen=True)
class JudgeEvalRunner:
    root: Path
    ruleset: RulesetLoader
    runs: Sequence[JudgeFactory]
    confidence_threshold: float
    ast_grep: AstGrep = AstGrep()

    def run(self) -> RuleTestResult:
        evals = JudgeEval.in_ruleset(self.ruleset.root)
        if not evals:
            return RuleTestResult()
        ruleset = self.ruleset.load()
        bindings = {binding.skill.name: binding for binding in Bindings.from_rulesets([ruleset])}
        scanner = SyntaxScanner.for_rulesets(self.ast_grep, [ruleset])
        problems: list[str] = []
        cases: list[_Case] = []
        for file, judge_eval in evals:
            where = file.relative_to(self.root)
            binding = bindings.get(judge_eval.id)
            if binding is None:
                problems.append(f"{where}: no judge rule {judge_eval.id}")
                continue
            cases.extend(
                _Case(binding, case, f"{where} {case.name}")
                for case in judge_eval.cases(Outcome.INVALID, Outcome.VALID)
            )
        with ExitStack() as stack:
            case_runs = [
                case_run
                for case in cases
                for case_run in case.runs(
                    stack.enter_context(EditRepo.of({case.file: case.numbered.edit})),
                    self.ast_grep,
                    ruleset,
                    self.runs,
                    scanner,
                )
            ]
            judged = self._judged(case_runs)
        return RuleTestResult.merge([RuleTestResult(problems=tuple(problems)), judged])

    def _judged(self, case_runs: list[_CaseRun]) -> RuleTestResult:
        if not case_runs:
            return RuleTestResult()
        with ThreadPoolExecutor(max_workers=len(case_runs)) as executor:
            return RuleTestResult.merge(executor.map(self._result, case_runs))

    def _result(self, case_run: _CaseRun) -> RuleTestResult:
        rule = case_run.binding.skill.name
        try:
            problem = case_run.problem(self.confidence_threshold)
        except JudgeError as error:
            return RuleTestResult(
                problems=(f"{self._where(case_run)}: {rule} not judged: {error}",)
            )
        if problem is None:
            return RuleTestResult()
        return RuleTestResult(problems=(f"{self._where(case_run)}: {rule} {problem}",))

    def _where(self, case_run: _CaseRun) -> str:
        where = case_run.name
        if len(self.runs) > 1:
            where += f" (run {case_run.run} of {len(self.runs)})"
        return where


@dataclass(frozen=True)
class _Case:
    binding: Binding
    numbered: NumberedCase
    name: str

    @property
    def file(self) -> str:
        return self.numbered.edit.file

    def runs(
        self,
        repo: EditRepo,
        ast_grep: AstGrep,
        ruleset: Ruleset,
        judges: Sequence[JudgeFactory],
        scanner: SyntaxScanner,
    ) -> list[_CaseRun]:
        judged = JudgeCase(file=self.file, violates=self.numbered.outcome == Outcome.INVALID)
        lines = repo.classified(ast_grep, ruleset).judged_lines(self.file)
        return [
            _CaseRun(self.binding, judged, self.name, repo.root, lines, factory, run, scanner)
            for run, factory in enumerate(judges, start=1)
        ]
