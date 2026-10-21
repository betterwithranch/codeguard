import subprocess
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from codeguard.ast_grep import AstGrep
from codeguard.config import Ruleset
from codeguard.rule_tests.judge_eval import EditCase
from codeguard.syntax import ChangeClassifier
from codeguard.working_tree import ChangedLines, WorkingTree


@dataclass(frozen=True)
class EditRepo:
    root: Path

    @classmethod
    @contextmanager
    def of(cls, edits: Mapping[str, EditCase]) -> Iterator[Self]:
        with tempfile.TemporaryDirectory() as directory:
            repo = cls(Path(directory))
            repo._git("init")
            repo._write(
                {path: edit.before for path, edit in edits.items() if edit.before is not None}
            )
            repo._git("add", "--all")
            repo._git("commit", "--allow-empty", "--message", "Before")
            repo._write({path: edit.after for path, edit in edits.items()})
            yield repo

    def classified(self, ast_grep: AstGrep, ruleset: Ruleset) -> ChangedLines:
        working_tree = WorkingTree(self.root)
        classifier = ChangeClassifier.for_rulesets(ast_grep, [ruleset], working_tree)
        return classifier.classify(working_tree.changed_lines("HEAD"))

    def _write(self, files: Mapping[str, str]) -> None:
        for path, text in files.items():
            file = self.root / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text)

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
