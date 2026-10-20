from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class JudgeProvider(StrEnum):
    CLAUDE_CLI = "claude-cli"
    GEMINI = "gemini"


class JudgeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: JudgeProvider = JudgeProvider.CLAUDE_CLI
    model: str | None = None
    project: str | None = None
    location: str | None = None

    @model_validator(mode="after")
    def validate_provider_settings(self) -> Self:
        if self.provider is JudgeProvider.GEMINI and self.model is None:
            raise ValueError("the gemini provider needs a model, such as gemini-3.8-flash")
        if self.provider is JudgeProvider.CLAUDE_CLI and (self.project or self.location):
            raise ValueError("project and location apply to the gemini provider only")
        return self

    def model_for(self, rule_model: str) -> str:
        return self.model or rule_model
