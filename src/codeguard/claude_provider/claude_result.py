import json
from collections.abc import Iterator
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

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
        messages = [json.loads(line) for line in stream.splitlines() if line.strip()]
        results = [message for message in messages if message["type"] == "result"]
        if not results:
            raise JudgeNoVerdict(f"claude printed no result:\n{stream}")
        windows = [
            message["rate_limit_info"].get("unifiedWindows", {})
            for message in messages
            if message["type"] == "rate_limit_event"
        ]
        tool_results = {
            content["tool_use_id"]: message.get("tool_use_result")
            for message in messages
            if message["type"] == "user"
            for content in _contents(message)
            if content.get("type") == "tool_result"
        }
        loaded_files = (
            file
            for message in messages
            if message["type"] == "assistant"
            for content in _contents(message)
            if content.get("type") == "tool_use"
            for file in _loaded_files(root, content, tool_results.get(content.get("id")))
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


def _contents(message: dict[str, object]) -> list[dict[str, object]]:
    body = message.get("message")
    content = body.get("content") if isinstance(body, dict) else None
    return [part for part in content if isinstance(part, dict)] if isinstance(content, list) else []


def _loaded_files(root: Path, call: dict[str, object], result: object) -> list[str]:
    """The files a tool call loaded: the file it read, or the files its search showed."""
    given = call.get("input")
    arguments = given if isinstance(given, dict) else {}
    if call.get("name") == "Read":
        path = arguments.get("file_path")
        files = [path] if isinstance(path, str) else []
    elif call.get("name") in _SEARCHES and isinstance(result, dict):
        searched = arguments.get("path")
        files = [
            *([searched] if isinstance(searched, str) and (root / searched).is_file() else []),
            *_strings(result.get("filenames")),
            *_files_in_lines(root, result.get("content")),
        ]
    else:
        files = []
    return [_relative(root, file) for file in files]


def _strings(values: object) -> list[str]:
    return [value for value in values if isinstance(value, str)] if isinstance(values, list) else []


def _files_in_lines(root: Path, content: object) -> Iterator[str]:
    if not isinstance(content, str):
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
