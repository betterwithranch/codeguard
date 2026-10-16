from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, DirectoryPath, Field, ValidationInfo, field_validator

SKILL_FILE = "SKILL.md"

type Severity = Literal["error", "warning", "info", "hint"]


class BindingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    skill: DirectoryPath
    paths: tuple[str, ...] = Field(min_length=1)
    severity: Severity = "error"

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
