from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from codeguard.config.config import Config

_CONFIG_DIR = ".codeguard"
_CONFIG_FILE = f"{_CONFIG_DIR}/config.yaml"
_BINDINGS_DIR = f"{_CONFIG_DIR}/bindings"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class ConfigLoader:
    root: Path

    def load(self) -> Config:
        config_file = self.root / _CONFIG_FILE
        settings = _read(config_file) if config_file.is_file() else {}
        bindings_dir = self.root / _BINDINGS_DIR
        bindings = {
            str(path.relative_to(bindings_dir)): _read(path)
            for path in sorted(bindings_dir.rglob("*.yaml"))
        }
        data = {**settings, "bindings": bindings} if isinstance(settings, dict) else settings
        try:
            return Config.model_validate(data, context={"working_tree": self.root})
        except ValidationError as error:
            problems = "".join(_problem(problem) for problem in error.errors(include_url=False))
            raise ConfigError(f"{self.root / _CONFIG_DIR} is invalid:{problems}") from error


def _read(path: Path) -> Any:
    return yaml.safe_load(path.read_text())


def _problem(problem: Any) -> str:
    location = ".".join(str(part) for part in problem["loc"])
    return f"\n  {location}: {problem['msg']}" if location else f"\n  {problem['msg']}"
