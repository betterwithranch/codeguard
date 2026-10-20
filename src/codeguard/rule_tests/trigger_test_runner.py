import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from codeguard.ast_grep import AstGrep
from codeguard.config import TRIGGER_TEST_DIR, ChangeKind, ConfigError, Ruleset, RulesetLoader
from codeguard.review import Binding, Bindings
from codeguard.rule_tests.rule_test_result import RuleTestResult
from codeguard.rule_tests.trigger_test import TRIGGER_TEST_GLOB, TriggerCase, TriggerTest
from codeguard.syntax import ChangeClassifier
from codeguard.working_tree import ChangedLines, WorkingTree


@dataclass(frozen=True)
class _CaseCheck:
    binding: Binding
    case: TriggerCase
    triggered: bool
    name: str
    path: str

    def problem(self, changed: ChangedLines) -> str | None:
        rule = self.binding.skill.name
        if not self.binding.files([self.case.file]):
            return f"{self.name}: {self.case.file} is outside the {rule} paths"
        kinds = changed.kinds_of(self.path)
        if kinds is None:
            return f"{self.name}: the case changes no code in {self.case.file}"
        fired = self.binding.is_triggered(changed, self.path)
        if fired == self.triggered:
            return None
        touched = ", ".join(sorted(kinds - {ChangeKind.ANY}))
        triggers = ", ".join(sorted(self.binding.triggers))
        verb = "miss" if self.triggered else "fire on"
        return f"{self.name}: {rule} triggers {triggers} {verb} the change, which touches {touched}"


@dataclass(frozen=True)
class TriggerTestRunner:
    root: Path
    ruleset: RulesetLoader
    ast_grep: AstGrep = AstGrep()

    @property
    def test_dir(self) -> Path:
        return self.ruleset.root / TRIGGER_TEST_DIR

    def run(self) -> RuleTestResult:
        if not self.test_dir.is_dir():
            return RuleTestResult()
        try:
            ruleset = self.ruleset.load()
        except ConfigError as error:
            return RuleTestResult(warnings=(f"trigger tests not run: {error}",))
        bindings = {binding.skill.name: binding for binding in Bindings.from_rulesets([ruleset])}
        tests = [
            (file.relative_to(self.root), TriggerTest.load(file))
            for file in sorted(self.test_dir.glob(TRIGGER_TEST_GLOB))
        ]
        unknown = [
            f"{where}: no judge rule {test.id}" for where, test in tests if test.id not in bindings
        ]
        checks = [
            check
            for where, test in tests
            if test.id in bindings
            for check in _case_checks(where, test, bindings[test.id])
        ]
        changed = _classify_changes(checks, self.ast_grep, ruleset)
        failed = [problem for check in checks if (problem := check.problem(changed))]
        return RuleTestResult(problems=(*unknown, *failed))


def _case_checks(where: Path, test: TriggerTest, binding: Binding) -> list[_CaseCheck]:
    return [
        _CaseCheck(
            binding,
            case,
            triggered,
            name=f"{where} {outcome} case {number}",
            path=f"{test.id}/{outcome}-{number}/{case.file}",
        )
        for triggered, outcome, cases in (
            (True, "triggered", test.triggered),
            (False, "skipped", test.skipped),
        )
        for number, case in enumerate(cases, start=1)
    ]


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
            {check.path: check.case.before for check in checks if check.case.before is not None}
        )
        repo.commit()
        repo.write({check.path: check.case.after for check in checks})
        working_tree = WorkingTree(repo.root)
        classifier = ChangeClassifier.for_rulesets(ast_grep, [ruleset], working_tree)
        return classifier.classify(working_tree.changed_lines("HEAD"))
