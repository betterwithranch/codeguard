from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from codeguard.config.config_error import ConfigError
from codeguard.config.config_loader import CONFIG_DIR
from codeguard.config.versions import VersionRange

LOCK_FILE = f"{CONFIG_DIR}/lock.yaml"


class LockedPackage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    git: str
    version: VersionRange
    ref: str

    def matches(self, git: str, version: VersionRange) -> bool:
        return self.git == git and self.version == version


class Lock(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    packages: tuple[LockedPackage, ...] = ()

    @classmethod
    def load(cls, working_tree: Path) -> Self:
        file = working_tree / LOCK_FILE
        if not file.is_file():
            return cls()
        try:
            return cls.model_validate(yaml.safe_load(file.read_text()))
        except ValidationError as error:
            raise ConfigError.invalid(file, error) from error

    def ref(self, git: str, version: VersionRange) -> str | None:
        return next((locked.ref for locked in self.packages if locked.matches(git, version)), None)

    def write(self, working_tree: Path) -> None:
        packages = [
            {"git": locked.git, "version": str(locked.version), "ref": locked.ref}
            for locked in self.packages
        ]
        text = yaml.safe_dump({"packages": packages}, sort_keys=False)
        (working_tree / LOCK_FILE).write_text(text)
