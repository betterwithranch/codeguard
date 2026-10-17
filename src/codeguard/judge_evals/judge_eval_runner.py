import shutil
import tempfile
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from codeguard.ast_grep import AstGrep
from codeguard.config import JUDGE_EVAL_DIR, RulesetLoader, Skip
from codeguard.judge_evals.eval_result import EvalResult
from codeguard.judge_evals.judge_case import JudgeCase
from codeguard.judge_evals.judge_eval import JudgeEval
from codeguard.review import Binding, Bindings, Judge, JudgeRequest
from codeguard.syntax import SourceTree

_EVAL_FILE_GLOB = "*-eval.yml"
_VARIANT_DESCRIPTIONS = {
    Skip.RENAMES: "with its names renamed",
    Skip.COMMENTS: "without comments",
    Skip.IMPORTS: "with its imports reordered",
}
_SKIPPED_CHANGES = {Skip.RENAMES: "names", Skip.COMMENTS: "comments", Skip.IMPORTS: "imports"}


class JudgeFactory(Protocol):
    def __call__(self, root: Path, model: str) -> Judge: ...


@dataclass(frozen=True)
class _CaseRun:
    binding: Binding
    case: JudgeCase
    path: Path
    directory: Path
    variant: Skip | None
    judges: JudgeFactory
    run: int

    def problem(self, confidence_threshold: float) -> str | None:
        if not (self.directory / self.case.file).is_file():
            return "no such file"
        judge = self.judges(self.directory, self.binding.model)
        verdict = judge.judge(JudgeRequest(self.binding.skill, self.case.file))
        return self.case.problem(verdict, confidence_threshold)


@dataclass(frozen=True)
class _Variant:
    directory: Path
    changed: frozenset[str]


@dataclass
class _Variants:
    ast_grep: AstGrep
    stack: ExitStack
    trees: dict[Path, SourceTree] = field(default_factory=dict)
    written: dict[tuple[Path, Skip], _Variant] = field(default_factory=dict)

    def of_case(self, binding: Binding, directory: Path, file: str) -> list[tuple[Skip, Path]]:
        if not directory.is_dir():
            return []
        variants = ((skip, self._variant(directory, skip)) for skip in binding.skips)
        return [(skip, variant.directory) for skip, variant in variants if file in variant.changed]

    def _variant(self, directory: Path, skip: Skip) -> _Variant:
        if (directory, skip) not in self.written:
            self.written[directory, skip] = self._write(directory, skip)
        return self.written[directory, skip]

    def _write(self, directory: Path, skip: Skip) -> _Variant:
        if directory not in self.trees:
            self.trees[directory] = SourceTree.scan(self.ast_grep, directory)
        changed = self.trees[directory].variant(skip)
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

    @property
    def eval_dir(self) -> Path:
        return self.ruleset.root / JUDGE_EVAL_DIR

    def run(self) -> EvalResult:
        if not self.eval_dir.is_dir():
            return EvalResult()
        bindings = {
            binding.skill.name: binding for binding in Bindings.from_rulesets([self.ruleset.load()])
        }
        problems: list[str] = []
        with ExitStack() as stack:
            variants = _Variants(self.ast_grep, stack)
            case_runs: list[_CaseRun] = []
            for file in sorted(self.eval_dir.glob(_EVAL_FILE_GLOB)):
                judge_eval = JudgeEval.load(file)
                binding = bindings.get(judge_eval.id)
                if binding is None:
                    problems.append(f"{file.relative_to(self.root)}: no judge rule {judge_eval.id}")
                    continue
                directory = self.eval_dir / judge_eval.id
                for case in judge_eval.cases():
                    case_runs.extend(self._case_runs(binding, directory, case, variants))
            problems.extend(self._problems(case_runs))
        return EvalResult(problems=tuple(problems))

    def _problems(self, case_runs: list[_CaseRun]) -> list[str]:
        if not case_runs:
            return []
        with ThreadPoolExecutor(max_workers=len(case_runs)) as executor:
            found = list(zip(case_runs, executor.map(self._problem, case_runs), strict=True))
        failed = {run.path for run, problem in found if problem and run.variant is None}
        return [
            problem
            for run, problem in found
            if problem and not (run.variant is not None and run.path in failed)
        ]

    def _case_runs(
        self, binding: Binding, directory: Path, case: JudgeCase, variants: _Variants
    ) -> list[_CaseRun]:
        path = directory / case.file
        sources = [(None, directory), *variants.of_case(binding, directory, case.file)]
        return [
            _CaseRun(binding, case, path, source, variant, judges, run)
            for variant, source in sources
            for run, judges in enumerate(self.runs, start=1)
        ]

    def _problem(self, case_run: _CaseRun) -> str | None:
        problem = case_run.problem(self.confidence_threshold)
        if problem is None:
            return None
        where = str(case_run.path.relative_to(self.root))
        if case_run.variant is not None:
            where += f" {_VARIANT_DESCRIPTIONS[case_run.variant]}"
        if len(self.runs) > 1:
            where += f" (run {case_run.run} of {len(self.runs)})"
        rule = case_run.binding.skill.name
        message = f"{where}: {rule} {problem}"
        if case_run.variant is not None:
            message += (
                f"\n  If {rule} judges {_SKIPPED_CHANGES[case_run.variant]}, "
                f"add {case_run.variant} to disable_skips in its binding."
            )
        return message
