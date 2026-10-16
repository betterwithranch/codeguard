from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Self

import yaml
from pydantic import ValidationError

from codeguard.config.bindings_config import BindingsConfig
from codeguard.config.config_error import ConfigError
from codeguard.config.config_loader import CONFIG_DIR, CONFIG_FILE
from codeguard.config.ruleset import BINDINGS_DIR, Ruleset
from codeguard.config.ruleset_config import RulesetConfig
from codeguard.config.ruleset_structure import RulesetStructure


@dataclass(frozen=True)
class RulesetLoader:
    repo: Path
    root: Path
    name: str | None = None
    selection: RulesetConfig = field(default_factory=RulesetConfig)
    files: frozenset[str] = frozenset()

    @classmethod
    def local(cls, working_tree: Path) -> Self:
        return cls(
            repo=working_tree,
            root=working_tree / CONFIG_DIR,
            files=frozenset({PurePath(CONFIG_FILE).name}),
        )

    def check(self) -> None:
        problems = RulesetStructure(self.root, self.files).problems()
        if problems:
            listed = "".join(f"\n  {problem}" for problem in problems)
            raise ConfigError(f"{self.root} is invalid:{listed}")

    def load(self) -> Ruleset:
        self.check()
        bindings_dir = self.root / BINDINGS_DIR
        bindings = {
            str(path.relative_to(bindings_dir)): yaml.safe_load(path.read_text())
            for path in sorted(bindings_dir.rglob("*.yaml"))
        }
        try:
            config = BindingsConfig.model_validate(bindings, context={"working_tree": self.repo})
        except ValidationError as error:
            raise ConfigError.invalid(self.root, error, prefix="bindings") from error
        return Ruleset(name=self.name, root=self.root, bindings=config, selection=self.selection)
