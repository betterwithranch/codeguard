from pydantic import BaseModel, ConfigDict, Field

from codeguard.config.judge_config import JudgeConfig
from codeguard.config.package_config import PackageConfig
from codeguard.config.versions import ExactVersion


class Config(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, arbitrary_types_allowed=True, validate_by_name=True
    )

    confidence_threshold: float = Field(default=0.9, ge=0, le=1)
    review_time_limit_minutes: int = Field(default=5, ge=1)
    ast_grep: ExactVersion | None = Field(default=None, alias="ast-grep")
    packages: tuple[PackageConfig, ...] = ()
    judge: JudgeConfig = JudgeConfig()
