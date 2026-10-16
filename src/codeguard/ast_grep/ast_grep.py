import sysconfig
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from codeguard.config import ConfigError

_DISTRIBUTION = "ast-grep-cli"
_BUNDLED = Path(sysconfig.get_path("scripts")) / "ast-grep"
SUPPORTED_AST_GREP = SpecifierSet(">=0.45")


@dataclass(frozen=True)
class AstGrep:
    pinned: Version | None = None

    @property
    def version(self) -> Version:
        return self.pinned or Version(metadata.version(_DISTRIBUTION))

    @property
    def executable(self) -> list[str | Path]:
        if self.pinned is None:
            return [_BUNDLED]
        return [
            "uv",
            "tool",
            "run",
            "--quiet",
            "--from",
            f"{_DISTRIBUTION}=={self.pinned}",
            "ast-grep",
        ]

    def check_supported(self) -> None:
        if not SUPPORTED_AST_GREP.contains(self.version, prereleases=True):
            raise ConfigError(
                f"codeguard supports ast-grep {SUPPORTED_AST_GREP}, not {self.version}"
            )
