from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from codeguard.config import JUDGE_EVAL_DIR, RulesetLoader
from codeguard.judge_evals.eval_result import EvalResult
from codeguard.judge_evals.judge_case import JudgeCase
from codeguard.judge_evals.judge_eval import JudgeEval
from codeguard.review import Binding, Bindings, Judge, JudgeRequest

_EVAL_FILE_GLOB = "*-eval.yml"


class JudgeFactory(Protocol):
    def __call__(self, root: Path, model: str) -> Judge: ...


@dataclass(frozen=True)
class _BoundCase:
    binding: Binding
    directory: Path
    case: JudgeCase

    @property
    def path(self) -> Path:
        return self.directory / self.case.file

    def problem(self, judges: JudgeFactory, confidence_threshold: float) -> str | None:
        if not self.path.is_file():
            return "no such file"
        judge = judges(self.directory, self.binding.model)
        verdict = judge.judge(JudgeRequest(self.binding.skill, self.case.file))
        return self.case.problem(verdict, confidence_threshold)


@dataclass(frozen=True)
class JudgeEvalRunner:
    root: Path
    ruleset: RulesetLoader
    judges: JudgeFactory
    confidence_threshold: float

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
        cases: list[_BoundCase] = []
        for file in sorted(self.eval_dir.glob(_EVAL_FILE_GLOB)):
            judge_eval = JudgeEval.load(file)
            binding = bindings.get(judge_eval.id)
            if binding is None:
                problems.append(f"{file.relative_to(self.root)}: no judge rule {judge_eval.id}")
                continue
            directory = self.eval_dir / judge_eval.id
            cases.extend(_BoundCase(binding, directory, case) for case in judge_eval.cases())
        if cases:
            with ThreadPoolExecutor(max_workers=len(cases)) as executor:
                found = executor.map(self._problem, cases)
                problems.extend(problem for problem in found if problem)
        return EvalResult(problems=tuple(problems))

    def _problem(self, bound: _BoundCase) -> str | None:
        problem = bound.problem(self.judges, self.confidence_threshold)
        if problem is None:
            return None
        return f"{bound.path.relative_to(self.root)}: {bound.binding.skill.name} {problem}"
