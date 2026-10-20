from dataclasses import dataclass
from functools import cached_property
from importlib.metadata import version
from pathlib import Path

from packaging.version import Version

from codeguard.ast_grep import AstGrep
from codeguard.config import Config, ConfigError, Lock, Ruleset, RulesetLoader
from codeguard.packages import MANIFEST_FILE, GitFetch, LatestRefs, LockedRefs, Manifest, Packages

_PACKAGE_CACHE_DIR = Path.home() / ".cache" / "codeguard" / "packages"
_CODEGUARD_VERSION = Version(version("codeguard"))


@dataclass(frozen=True)
class RulesetResolver:
    root: Path
    config: Config
    ast_grep: AstGrep
    latest: bool = False

    @cached_property
    def rulesets(self) -> tuple[Ruleset, ...]:
        refs = LatestRefs() if self.latest else LockedRefs(Lock.load(self.root))
        packages = Packages(
            self.root, GitFetch(_PACKAGE_CACHE_DIR), self.ast_grep.version, _CODEGUARD_VERSION, refs
        )
        return (RulesetLoader.local(self.root).load(), *packages.rulesets(self.config.packages))

    @cached_property
    def own_rulesets(self) -> list[RulesetLoader]:
        manifest = Manifest.in_repo(self.root)
        loaders = [RulesetLoader.local(self.root)]
        if manifest:
            for problem in (
                manifest.codeguard_problem(_CODEGUARD_VERSION),
                manifest.ast_grep_problem(self.ast_grep.version),
            ):
                if problem:
                    raise ConfigError(f"{self.root / MANIFEST_FILE} is invalid:\n  {problem}")
            loaders.extend(
                RulesetLoader(repo=self.root, root=self.root / name, name=f"{manifest.name}/{name}")
                for name in manifest.rulesets
            )
        for loader in loaders:
            loader.check()
        return loaders
