import json
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from codeguard.review import JudgeNoVerdict, Verdict


class ModelUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int = Field(alias="inputTokens")
    output_tokens: int = Field(alias="outputTokens")
    cache_read_input_tokens: int = Field(alias="cacheReadInputTokens")
    cache_creation_input_tokens: int = Field(alias="cacheCreationInputTokens")
    thinking_tokens: int = Field(alias="thinkingTokens")
    cost_usd: float = Field(alias="costUSD")


class UsageWindow(BaseModel):
    model_config = ConfigDict(frozen=True)

    utilization: float


class ToolUse(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    input: dict[str, object]

    def read_file(self, root: Path) -> str | None:
        path = self.input.get("file_path")
        if self.name != "Read" or not isinstance(path, str):
            return None
        resolved = (root / path).resolve()
        if resolved.is_relative_to(root.resolve()):
            return str(resolved.relative_to(root.resolve()))
        return path


class ClaudeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_error: bool
    subtype: str
    num_turns: int
    duration_ms: int
    duration_api_ms: int
    total_cost_usd: float
    model_usage: dict[str, ModelUsage] = Field(alias="modelUsage")
    usage_windows: dict[str, UsageWindow] = Field(alias="usageWindows")
    structured_output: Verdict | None = None
    tool_uses: tuple[ToolUse, ...] = ()

    @classmethod
    def from_stream(cls, stream: str) -> Self:
        messages = [json.loads(line) for line in stream.splitlines() if line.strip()]
        results = [message for message in messages if message["type"] == "result"]
        if not results:
            raise JudgeNoVerdict(f"claude printed no result:\n{stream}")
        windows = [
            message["rate_limit_info"].get("unifiedWindows", {})
            for message in messages
            if message["type"] == "rate_limit_event"
        ]
        tool_uses = [
            content
            for message in messages
            if message["type"] == "assistant"
            for content in message["message"]["content"]
            if content["type"] == "tool_use"
        ]
        return cls.model_validate(
            {
                **results[-1],
                "usageWindows": windows[-1] if windows else {},
                "tool_uses": tool_uses,
            }
        )

    def read_files(self, root: Path) -> tuple[str, ...]:
        return tuple(file for use in self.tool_uses if (file := use.read_file(root)) is not None)

    @property
    def telemetry(self) -> dict[str, object]:
        usages = self.model_usage.values()
        return {
            "is_error": self.is_error,
            "subtype": self.subtype,
            "num_turns": self.num_turns,
            "duration_ms": self.duration_ms,
            "duration_api_ms": self.duration_api_ms,
            "cost_usd": self.total_cost_usd,
            "input_tokens": sum(usage.input_tokens for usage in usages),
            "output_tokens": sum(usage.output_tokens for usage in usages),
            "cache_read_input_tokens": sum(usage.cache_read_input_tokens for usage in usages),
            "cache_creation_input_tokens": sum(
                usage.cache_creation_input_tokens for usage in usages
            ),
            "thinking_tokens": sum(usage.thinking_tokens for usage in usages),
            "model_usage": {model: usage.model_dump() for model, usage in self.model_usage.items()},
            **{
                f"{window}_utilization": usage.utilization
                for window, usage in self.usage_windows.items()
            },
        }
