from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from codeguard.config.config import Config
from codeguard.config.config_error import ConfigError

CONFIG_DIR = ".codeguard"
CONFIG_FILE = f"{CONFIG_DIR}/config.yaml"


@dataclass(frozen=True)
class ConfigLoader:
    root: Path

    def load(self) -> Config:
        config_file = self.root / CONFIG_FILE
        settings = yaml.safe_load(config_file.read_text()) if config_file.is_file() else {}
        try:
            return Config.model_validate(settings, context={"working_tree": self.root})
        except ValidationError as error:
            raise ConfigError.invalid(self.root / CONFIG_DIR, error) from error
