import os
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Gemini's pay-as-you-go capacity is shared, so fewer calls at once keep a run under its
# tokens-per-minute limit.
_GEMINI_CALLS_AT_ONCE = 2
# A rule is judged with the model its evals pass on, so only its binding names one.
_RETIRED_FIELDS = {
    "provider": "a rule's binding names its provider",
    "model": "a rule's binding names its model",
}


class JudgeProvider(StrEnum):
    CLAUDE_CLI = "claude-cli"
    GEMINI = "gemini"


class JudgeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: JudgeProvider
    name: str


class JudgeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project: str | None = None
    location: str | None = None
    calls_at_once: int | None = Field(default=None, ge=1)

    @model_validator(mode="before")
    @classmethod
    def reject_retired_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            retired = [f"judge.{key}: {why}" for key, why in _RETIRED_FIELDS.items() if key in data]
            if retired:
                raise ValueError("; ".join(retired))
        return data

    def concurrency(self, provider: JudgeProvider) -> int:
        if self.calls_at_once is not None:
            return self.calls_at_once
        if provider is JudgeProvider.GEMINI:
            return _GEMINI_CALLS_AT_ONCE
        return os.process_cpu_count() or 1
