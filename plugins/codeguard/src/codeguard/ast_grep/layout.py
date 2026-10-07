import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import yaml

RULE_DIR = ".codeguard/rules/pattern"
TEST_DIR = ".codeguard/rule-tests/pattern"


@dataclass(frozen=True)
class Layout:
    root: Path

    @property
    def rule_dir(self) -> Path:
        return self.root / RULE_DIR

    @property
    def test_dir(self) -> Path:
        return self.root / TEST_DIR

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
