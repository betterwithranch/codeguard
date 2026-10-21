import os
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Gemini's pay-as-you-go capacity is shared, so fewer calls at once keep a run under its
# tokens-per-minute limit.
_GEMINI_CALLS_AT_ONCE = 2


class JudgeProvider(StrEnum):
    CLAUDE_CLI = "claude-cli"
    GEMINI = "gemini"


class JudgeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: JudgeProvider = JudgeProvider.CLAUDE_CLI
    model: str | None = None
    project: str | None = None
    location: str | None = None
    calls_at_once: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_provider_settings(self) -> Self:
        if self.provider is JudgeProvider.GEMINI and self.model is None:
            raise ValueError("the gemini provider needs a model, such as gemini-3.1-pro-preview")
        if self.provider is JudgeProvider.CLAUDE_CLI and (self.project or self.location):
            raise ValueError("project and location apply to the gemini provider only")
        return self

    @property
    def concurrency(self) -> int:
        if self.calls_at_once is not None:
            return self.calls_at_once
        if self.provider is JudgeProvider.GEMINI:
            return _GEMINI_CALLS_AT_ONCE
        return os.process_cpu_count() or 1

    def model_for(self, rule_model: str) -> str:
        return self.model or rule_model
