import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from codeguard.ast_grep import AstGrep
from codeguard.config import ChangeKind, ConfigError, Ruleset, RulesetLoader
from codeguard.review import Binding, Bindings
from codeguard.rule_tests.judge_eval import JudgeEval, NumberedCase, Outcome
from codeguard.rule_tests.rule_test_result import RuleTestResult
from codeguard.syntax import ChangeClassifier
from codeguard.working_tree import ChangedLines, WorkingTree


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


@dataclass(frozen=True)
class _ScratchRepo:
    root: Path

    @classmethod
    def init(cls, root: Path) -> Self:
        repo = cls(root)
        repo._git("init")
        return repo

    def write(self, files: Mapping[str, str]) -> None:
        for path, text in files.items():
            file = self.root / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text)

    def commit(self) -> None:
        self._git("add", "--all")
        self._git("commit", "--allow-empty", "--message", "Before")

    def _git(self, *args: str) -> None:
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=codeguard",
                "-c",
                "user.email=codeguard@localhost",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            cwd=self.root,
            check=True,
            capture_output=True,
        )


def _classify_changes(
    checks: Sequence[_CaseCheck], ast_grep: AstGrep, ruleset: Ruleset
) -> ChangedLines:
    with tempfile.TemporaryDirectory() as directory:
        repo = _ScratchRepo.init(Path(directory))
        repo.write(
            {
                check.path: check.case.edit.before
                for check in checks
                if check.case.edit.before is not None
            }
        )
        repo.commit()
        repo.write({check.path: check.case.edit.after for check in checks})
        working_tree = WorkingTree(repo.root)
        classifier = ChangeClassifier.for_rulesets(ast_grep, [ruleset], working_tree)
        return classifier.classify(working_tree.changed_lines("HEAD"))
