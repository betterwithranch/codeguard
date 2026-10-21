from pathlib import Path

from pydantic import BaseModel, ConfigDict, DirectoryPath, Field, ValidationInfo, field_validator

from codeguard.config.change_kind import ChangeKind
from codeguard.config.severity import Severity

SKILL_FILE = "SKILL.md"


class BindingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    skill: DirectoryPath
    paths: tuple[str, ...] = Field(min_length=1)
    exclude_paths: tuple[str, ...] = ()
    severity: Severity = Severity.ERROR
    model: str = "claude-sonnet-5-5"
    triggers: frozenset[str] = Field(frozenset({ChangeKind.ANY}), min_length=1)

    @field_validator("skill", mode="before")
    @classmethod
    def resolve_skill_in_working_tree(cls, skill: object, info: ValidationInfo) -> object:
        if not isinstance(skill, str | Path):
            return skill
        working_tree = (info.context or {}).get("working_tree", Path())
        return working_tree / skill

    @field_validator("skill")
    @classmethod
    def validate_skill_file_exists(cls, skill: Path) -> Path:
        if not (skill / SKILL_FILE).is_file():
            raise ValueError(f"{skill} has no {SKILL_FILE}")
        return skill
