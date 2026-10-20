import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Self

import yaml

from codeguard.ast_grep import AstGrep
from codeguard.config import GATE_DIR, GATE_TEST_DIR, PATTERN_RULE_DIR, PATTERN_TEST_DIR


@dataclass(frozen=True)
class Layout:
    root: Path
    ruleset: Path
    ast_grep: AstGrep = AstGrep()
    rule_dir_name: str = PATTERN_RULE_DIR
    test_dir_name: str = PATTERN_TEST_DIR

    @classmethod
    def gates(cls, root: Path, ruleset: Path, ast_grep: AstGrep) -> Self:
        return cls(root, ruleset, ast_grep, GATE_DIR, GATE_TEST_DIR)

    @property
    def rule_dir(self) -> Path:
        return self.ruleset / self.rule_dir_name

    @property
    def test_dir(self) -> Path:
        return self.ruleset / self.test_dir_name

    def has_rules(self) -> bool:
        return self.rule_dir.is_dir()

    def has_tests(self) -> bool:
        return self.has_rules() and self.test_dir.is_dir()

    @contextmanager
    def config(self) -> Iterator[Path]:
        settings = {
            "ruleDirs": [str(self.rule_dir)],
            "testConfigs": [{"testDir": str(self.test_dir)}],
        }
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "sgconfig.yml"
            config.write_text(yaml.safe_dump(settings))
            yield config
