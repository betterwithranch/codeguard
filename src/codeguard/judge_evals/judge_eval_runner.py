import shutil
import tempfile
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass, field, replace
from pathlib import Path

from codeguard.ast_grep import AstGrep
from codeguard.config import ChangeKind, RulesetLoader, Skip
from codeguard.judge_evals.code_variants import CodeVariants
from codeguard.judge_evals.judge_case import JudgeCase
from codeguard.judge_evals.judge_factory import JudgeFactory
from codeguard.review import Binding, Bindings, JudgeError, JudgeRequest, Verdict
from codeguard.rule_tests import JudgeEval, NumberedCase, Outcome, RuleTestResult
from codeguard.syntax import SyntaxScanner

_VARIANT_DESCRIPTIONS = {
    Skip.RENAMES: "with its names renamed",
    Skip.COMMENTS: "without comments",
    Skip.IMPORTS: "with its imports reordered",
}
_SKIPPED_CHANGES = {Skip.RENAMES: "names", Skip.COMMENTS: "comments", Skip.IMPORTS: "imports"}


@dataclass(frozen=True)
class _CaseRun:
    binding: Binding
    case: JudgeCase
    name: str
    directory: Path
    variant: Skip | None
    judges: JudgeFactory
    run: int
    scanner: SyntaxScanner

    def problem(self, confidence_threshold: float) -> str | None:
        judge = self.judges(self.directory, self.binding.model)
        verdict = judge.judge(JudgeRequest.read(self.binding.skill, self.directory, self.case.file))
        return self.case.problem(verdict, confidence_threshold) or self._trigger_problem(
            verdict, confidence_threshold
        )

    def _trigger_problem(self, verdict: Verdict, confidence_threshold: float) -> str | None:
        if (
            self.variant is not None
            or not self.case.violates
            or ChangeKind.ANY in self.binding.triggers
        ):
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
class _Variant:
    directory: Path
    changed: frozenset[str]


@dataclass
class _Variants:
    ast_grep: AstGrep
    stack: ExitStack
    code: dict[Path, CodeVariants] = field(default_factory=dict)
    written: dict[tuple[Path, Skip], _Variant] = field(default_factory=dict)

    def of_case(self, binding: Binding, directory: Path, file: str) -> list[tuple[Skip, Path]]:
        variants = ((skip, self._variant(directory, skip)) for skip in binding.skips)
        return [(skip, variant.directory) for skip, variant in variants if file in variant.changed]

    def _variant(self, directory: Path, skip: Skip) -> _Variant:
        if (directory, skip) not in self.written:
            self.written[directory, skip] = self._write(directory, skip)
        return self.written[directory, skip]

    def _write(self, directory: Path, skip: Skip) -> _Variant:
        if directory not in self.code:
            self.code[directory] = CodeVariants(SyntaxScanner(self.ast_grep).scan(directory))
        changed = self.code[directory].variant(skip)
        if not changed:
            return _Variant(directory, frozenset())
        variant = Path(self.stack.enter_context(tempfile.TemporaryDirectory())) / directory.name
        shutil.copytree(directory, variant)
        for file, content in changed.items():
            (variant / file).write_bytes(content)
        return _Variant(variant, frozenset(changed))


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
        judged = RuleTestResult()
        with ExitStack() as stack:
            variants = _Variants(self.ast_grep, stack)
            case_runs: list[_CaseRun] = []
            for file, judge_eval in evals:
                where = file.relative_to(self.root)
                binding = bindings.get(judge_eval.id)
                if binding is None:
                    problems.append(f"{where}: no judge rule {judge_eval.id}")
                    continue
                for case in judge_eval.cases(Outcome.INVALID, Outcome.VALID):
                    name = f"{where} {case.name}"
                    case_runs.extend(self._case_runs(binding, case, name, variants, scanner))
            judged = self._judged(case_runs)
        return RuleTestResult.merge([RuleTestResult(problems=tuple(problems)), judged])

    def _judged(self, case_runs: list[_CaseRun]) -> RuleTestResult:
        if not case_runs:
            return RuleTestResult()
        with ThreadPoolExecutor(max_workers=len(case_runs)) as executor:
            found = list(zip(case_runs, executor.map(self._result, case_runs), strict=True))
        failed = {run.name for run, result in found if result.problems and run.variant is None}
        return RuleTestResult.merge(
            replace(result, problems=())
            if run.variant is not None and run.name in failed
            else result
            for run, result in found
        )

    def _case_runs(
        self,
        binding: Binding,
        case: NumberedCase,
        name: str,
        variants: _Variants,
        scanner: SyntaxScanner,
    ) -> list[_CaseRun]:
        directory = _written(variants.stack, case)
        judged = JudgeCase(file=case.edit.file, violates=case.outcome == Outcome.INVALID)
        sources = [(None, directory), *variants.of_case(binding, directory, judged.file)]
        return [
            _CaseRun(binding, judged, name, source, variant, judges, run, scanner)
            for variant, source in sources
            for run, judges in enumerate(self.runs, start=1)
        ]

    def _result(self, case_run: _CaseRun) -> RuleTestResult:
        rule = case_run.binding.skill.name
        try:
            problem = case_run.problem(self.confidence_threshold)
        except JudgeError as error:
            return RuleTestResult(
                warnings=(f"{self._where(case_run)}: {rule} not judged: {error}",)
            )
        if problem is None:
            return RuleTestResult()
        message = f"{self._where(case_run)}: {rule} {problem}"
        if case_run.variant is not None:
            message += (
                f"\n  If {rule} judges {_SKIPPED_CHANGES[case_run.variant]}, "
                f"add {case_run.variant} to disable_skips in its binding."
            )
        return RuleTestResult(problems=(message,))

    def _where(self, case_run: _CaseRun) -> str:
        where = case_run.name
        if case_run.variant is not None:
            where += f" {_VARIANT_DESCRIPTIONS[case_run.variant]}"
        if len(self.runs) > 1:
            where += f" (run {case_run.run} of {len(self.runs)})"
        return where


def _written(stack: ExitStack, case: NumberedCase) -> Path:
    directory = Path(stack.enter_context(tempfile.TemporaryDirectory())) / case.directory
    file = directory / case.edit.file
    file.parent.mkdir(parents=True)
    file.write_text(case.edit.after)
    return directory
