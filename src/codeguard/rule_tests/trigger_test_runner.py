from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from codeguard.ast_grep import AstGrep
from codeguard.config import ChangeKind, ConfigError, Ruleset, RulesetLoader
from codeguard.review import Binding, Bindings
from codeguard.rule_tests.edit_repo import EditRepo
from codeguard.rule_tests.judge_eval import JudgeEval, NumberedCase, Outcome
from codeguard.rule_tests.rule_test_result import RuleTestResult
from codeguard.working_tree import ChangedLines


@dataclass(frozen=True)
class _CaseCheck:
    binding: Binding
    case: NumberedCase
    name: str
    path: str

    def problem(self, changed: ChangedLines) -> str | None:
        rule = self.binding.skill.name
        file = self.case.edit.file
        if not self.binding.files([file]):
            return f"{self.name}: {file} is outside the {rule} paths"
        kinds = changed.kinds_of(self.path)
        if kinds is None:
            return f"{self.name}: the case changes no code in {file}"
        if self.case.outcome == Outcome.VALID:
            return None
        should_fire = self.case.outcome == Outcome.INVALID
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
        evals = JudgeEval.in_ruleset(self.ruleset.root)
        if not evals:
            return RuleTestResult()
        try:
            ruleset = self.ruleset.load()
        except ConfigError as error:
            return RuleTestResult(warnings=(f"trigger tests not run: {error}",))
        bindings = {binding.skill.name: binding for binding in Bindings.from_rulesets([ruleset])}
        named = [(file.relative_to(self.root), judge_eval) for file, judge_eval in evals]
        unknown = [
            f"{where}: no judge rule {judge_eval.id}"
            for where, judge_eval in named
            if judge_eval.id not in bindings
        ]
        checks = [
            _CaseCheck(
                bindings[judge_eval.id],
                case,
                name=f"{where} {case.name}",
                path=f"{judge_eval.id}/{case.directory}/{case.edit.file}",
            )
            for where, judge_eval in named
            if judge_eval.id in bindings
            for case in judge_eval.cases()
        ]
        changed = _classify_changes(checks, self.ast_grep, ruleset)
        failed = [problem for check in checks if (problem := check.problem(changed))]
        return RuleTestResult(problems=(*unknown, *failed))


def _classify_changes(
    checks: Sequence[_CaseCheck], ast_grep: AstGrep, ruleset: Ruleset
) -> ChangedLines:
    with EditRepo.of({check.path: check.case.edit for check in checks}) as repo:
        return repo.classified(ast_grep, ruleset)
