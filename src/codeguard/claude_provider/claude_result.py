import json
from collections.abc import Iterator
from pathlib import Path
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidatorFunctionWrapHandler,
    field_validator,
)

from codeguard.review import JudgeNoVerdict, Verdict

_SEARCHES = frozenset({"Grep", "Glob"})


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


class _RateLimitInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    unified_windows: dict[str, UsageWindow] = Field(default_factory=dict, alias="unifiedWindows")


class _SearchResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    filenames: tuple[str, ...] = ()
    content: str | None = None


class _ToolInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    file_path: str | None = None
    path: str | None = None


class _ContentPart(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: str
    id: str | None = None
    name: str | None = None
    input: _ToolInput = _ToolInput()
    tool_use_id: str | None = None

    def loaded_files(self, root: Path, result: _SearchResult | None) -> list[str]:
        """The files this tool call loaded: the file it read, or the files its search showed."""
        if self.name == "Read":
            files = [] if self.input.file_path is None else [self.input.file_path]
        elif self.name in _SEARCHES and result is not None:
            searched = self.input.path
            files = [
                *([searched] if searched is not None and (root / searched).is_file() else []),
                *result.filenames,
                *_files_in_lines(root, result.content),
            ]
        else:
            files = []
        return [_relative(root, file) for file in files]


class _MessageBody(BaseModel):
    model_config = ConfigDict(frozen=True)

    content: tuple[_ContentPart, ...] = ()

    @field_validator("content", mode="before")
    @classmethod
    def _text_has_no_parts(cls, content: object) -> object:
        return content if isinstance(content, list) else ()


class _StreamMessage(BaseModel):
    """One line of claude's stream-json output, holding only the fields the judge reads."""

    model_config = ConfigDict(frozen=True)

    type: str
    message: _MessageBody = _MessageBody()
    tool_use_result: _SearchResult | None = None
    rate_limit_info: _RateLimitInfo | None = None

    @field_validator("tool_use_result", mode="wrap")
    @classmethod
    def _only_search_results(
        cls, result: object, handler: ValidatorFunctionWrapHandler
    ) -> _SearchResult | None:
        try:
            return handler(result)
        except ValidationError:
            return None


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
    loaded_files: tuple[str, ...] = ()

    @classmethod
    def from_stream(cls, stream: str, root: Path) -> Self:
        lines = [json.loads(line) for line in stream.splitlines() if line.strip()]
        messages = [_StreamMessage.model_validate(line) for line in lines]
        results = [
            line for line, message in zip(lines, messages, strict=True) if message.type == "result"
        ]
        if not results:
            raise JudgeNoVerdict(f"claude printed no result:\n{stream}")
        windows = [
            message.rate_limit_info.unified_windows
            for message in messages
            if message.rate_limit_info is not None
        ]
        tool_results = {
            part.tool_use_id: message.tool_use_result
            for message in messages
            if message.type == "user"
            for part in message.message.content
            if part.type == "tool_result"
        }
        loaded_files = (
            file
            for message in messages
            if message.type == "assistant"
            for part in message.message.content
            if part.type == "tool_use"
            for file in part.loaded_files(root, tool_results.get(part.id))
        )
        return cls.model_validate(
            {
                **results[-1],
                "usageWindows": windows[-1] if windows else {},
                "loaded_files": tuple(dict.fromkeys(loaded_files)),
            }
        )

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


def _files_in_lines(root: Path, content: str | None) -> Iterator[str]:
    if content is None:
        return
    for line in content.splitlines():
        prefixes = (line[:end] for end, char in enumerate(line) if char in ":-")
        file = next((prefix for prefix in prefixes if (root / prefix).is_file()), None)
        if file is not None:
            yield file


def _relative(root: Path, path: str) -> str:
    resolved = (root / path).resolve()
    if resolved.is_relative_to(root.resolve()):
        return str(resolved.relative_to(root.resolve()))
    return path
