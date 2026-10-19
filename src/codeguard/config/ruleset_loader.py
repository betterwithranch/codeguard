from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Self

import yaml
from pydantic import ValidationError

from codeguard.config.bindings_config import BindingsConfig
from codeguard.config.config_error import ConfigError
from codeguard.config.config_loader import CONFIG_DIR, CONFIG_FILE
from codeguard.config.lock import LOCK_FILE
from codeguard.config.pattern_binding_config import PatternBindingsConfig
from codeguard.config.ruleset import BINDINGS_DIR, Ruleset
from codeguard.config.ruleset_config import RulesetConfig
from codeguard.config.ruleset_structure import RulesetStructure

_PATTERN_BINDING_KEY = "rule"


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
            files=frozenset({PurePath(CONFIG_FILE).name, PurePath(LOCK_FILE).name}),
        )

    def check(self) -> None:
        problems = RulesetStructure(self.root, self.files).problems()
        if problems:
            listed = "".join(f"\n  {problem}" for problem in problems)
            raise ConfigError(f"{self.root} is invalid:{listed}")

    def load(self) -> Ruleset:
        self.check()
        bindings_dir = self.root / BINDINGS_DIR
        documents = {
            str(path.relative_to(bindings_dir)): yaml.safe_load(path.read_text())
            for path in sorted(bindings_dir.rglob("*.yaml"))
        }
        pattern_documents = {
            file: document
            for file, document in documents.items()
            if isinstance(document, dict) and _PATTERN_BINDING_KEY in document
        }
        skill_documents = {
            file: document for file, document in documents.items() if file not in pattern_documents
        }
        try:
            bindings = BindingsConfig.model_validate(
                skill_documents, context={"working_tree": self.repo}
            )
            pattern_bindings = PatternBindingsConfig.model_validate(pattern_documents)
        except ValidationError as error:
            raise ConfigError.invalid(self.root, error, prefix="bindings") from error
        ruleset = Ruleset(
            name=self.name,
            root=self.root,
            bindings=bindings,
            selection=self.selection,
            pattern_bindings=pattern_bindings,
        )
        self._check_bound_pattern_rules(ruleset)
        return ruleset

    def _check_bound_pattern_rules(self, ruleset: Ruleset) -> None:
        if not ruleset.pattern_bindings.root:
            return
        rules = ruleset.pattern_rule_ids()
        problems = [
            f"bindings.{file}.rule: no pattern rule {binding.rule}"
            for file, binding in ruleset.pattern_bindings.root.items()
            if binding.rule not in rules
        ]
        if problems:
            listed = "".join(f"\n  {problem}" for problem in problems)
            raise ConfigError(f"{self.root} is invalid:{listed}")
