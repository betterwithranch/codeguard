from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    DirectoryPath,
    Field,
    ValidationInfo,
    field_validator,
)

from codeguard.config.ruleset_config import RulesetConfig
from codeguard.config.versions import VersionRange


class GitPackageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["git"] = "git"
    git: str
    ref: str
    rulesets: dict[str, RulesetConfig] = Field(min_length=1)


class VersionedPackageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    kind: Literal["versioned"] = "versioned"
    git: str
    version: VersionRange
    rulesets: dict[str, RulesetConfig] = Field(min_length=1)


class PathPackageConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["path"] = "path"
    path: DirectoryPath
    rulesets: dict[str, RulesetConfig] = Field(min_length=1)

    @field_validator("path", mode="before")
    @classmethod
    def resolve_path_in_working_tree(cls, path: object, info: ValidationInfo) -> object:
        if not isinstance(path, str | Path):
            return path
        working_tree = (info.context or {}).get("working_tree", Path())
        return (working_tree / path).resolve()


type PackageConfig = Annotated[
    GitPackageConfig | VersionedPackageConfig | PathPackageConfig, Field(discriminator="kind")
]
