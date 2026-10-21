import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from pydantic_evals import Case

from codeguard.ast_grep import AstGrep
from codeguard.config import ChangeKind, ConfigError, Ruleset, RulesetLoader
from codeguard.review import Binding, Bindings
from codeguard.rule_tests.rule_eval import EditCase, EditReview, Outcome, rule_evals
from codeguard.rule_tests.rule_test_result import RuleTestResult
from codeguard.rule_tests.scratch_repo import ScratchRepo
from codeguard.syntax import ChangeClassifier
from codeguard.working_tree import ChangedLines, WorkingTree

_JUDGED = frozenset({Outcome.INVALID, Outcome.UNCERTAIN})


@dataclass(frozen=True)
class _CaseCheck:
    binding: Binding
    case: Case[EditCase, EditReview, None]
    name: str
    path: str

    def problem(self, changed: ChangedLines) -> str | None:
        rule = self.binding.skill.name
        file = self.case.inputs.file
        expected = self.case.expected_output
        if not self.binding.files([file]):
            return f"{self.name}: {file} is outside the {rule} paths"
        kinds = changed.kinds_of(self.path)
        if kinds is None:
            return f"{self.name}: the case changes no code in {file}"
        if expected is None or expected.outcome is Outcome.VALID:
            return None
        should_fire = expected.outcome in _JUDGED
        if self.binding.is_triggered(changed, self.path) == should_fire:
            return None
        touched = ", ".join(sorted(kinds - {ChangeKind.ANY}))
        triggers = ", ".join(sorted(self.binding.triggers))
        verb = "miss" if should_fire else "fire on"
        return f"{self.name}: {rule} triggers {triggers} {verb} the change, which touches {touched}"


@dataclass(frozen=True)
class TriggerTestRunner:
    root: Path
    ruleset: RulesetLoader
    ast_grep: AstGrep = AstGrep()

    def run(self) -> RuleTestResult:
        try:
            evals = rule_evals(self.ruleset.root)
            if not evals:
                return RuleTestResult()
            ruleset = self.ruleset.load()
        except ConfigError as error:
            return RuleTestResult(warnings=(f"trigger tests not run: {error}",))
        bindings = {binding.skill.name: binding for binding in Bindings.from_rulesets([ruleset])}
        named = [(file.relative_to(self.root), dataset) for file, dataset in evals]
        unknown = [
            f"{where}: no judge rule {dataset.name}"
            for where, dataset in named
            if dataset.name not in bindings
        ]
        checks = [
            _CaseCheck(
                bindings[dataset.name],
                case,
                name=f"{where} {case.name}",
                path=f"{dataset.name}/{number}/{case.inputs.file}",
            )
            for where, dataset in named
            if dataset.name in bindings
            for number, case in enumerate(dataset.cases, start=1)
        ]
        changed = _classify_changes(checks, self.ast_grep, ruleset)
        failed = [problem for check in checks if (problem := check.problem(changed))]
        return RuleTestResult(problems=(*unknown, *failed))


def _classify_changes(
    checks: Sequence[_CaseCheck], ast_grep: AstGrep, ruleset: Ruleset
) -> ChangedLines:
    with tempfile.TemporaryDirectory() as directory:
        repo = ScratchRepo.init(Path(directory))
        repo.write(
            {
                check.path: check.case.inputs.before
                for check in checks
                if check.case.inputs.before is not None
            }
        )
        repo.commit()
        repo.write({check.path: check.case.inputs.after for check in checks})
        working_tree = WorkingTree(repo.root)
        classifier = ChangeClassifier.for_rulesets(ast_grep, [ruleset], working_tree)
        return classifier.classify(working_tree.changed_lines("HEAD"))
