import time
from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from itertools import accumulate
from pathlib import Path
from typing import Protocol

import httpx
import logfire
from google.genai import errors, types
from pydantic import ValidationError

from codeguard.gemini_provider.file_tools import FileTools
from codeguard.gemini_provider.gemini_usage import GeminiUsage
from codeguard.review import (
    Deadline,
    JudgeNoVerdict,
    JudgeProcessError,
    JudgeRequest,
    JudgeTimeout,
    Verdict,
)

_PROVIDER = "gemini"
_MAX_TURNS = 25
_REQUEST_LIMIT_SECONDS = 120
_MAX_ATTEMPTS = 12
_SUBMIT_VERDICT = types.FunctionDeclaration(
    name="submit_verdict",
    description="Report the violations in the file under review. Call it once, last.",
    parameters_json_schema=Verdict.model_json_schema(),
)


class GeminiModels(Protocol):
    def generate_content_stream(
        self, *, model: str, contents: list[types.Content], config: types.GenerateContentConfig
    ) -> Iterator[types.GenerateContentResponse]: ...


class GeminiClient(Protocol):
    @property
    def models(self) -> GeminiModels: ...


@dataclass(frozen=True)
class GeminiJudge:
    root: Path
    model: str
    client: GeminiClient
    processes: AbstractContextManager[object]
    deadline: Deadline | None = None
    max_turns: int = _MAX_TURNS
    request_limit_seconds: float = _REQUEST_LIMIT_SECONDS

    @property
    def identity(self) -> str:
        return "\0".join((_PROVIDER, self.model))

    def judge(self, request: JudgeRequest) -> Verdict:
        with logfire.span(
            "gemini judges {rule} on {file}",
            rule=request.skill.name,
            file=request.file,
            model=self.model,
        ) as span:
            instructions = request.instructions((self.root / request.file).read_text())
            usage = GeminiUsage()
            try:
                with self.processes:
                    return self._converse(instructions, request.prompt, usage)
            finally:
                span.set_attributes(usage.telemetry)

    def _converse(self, instructions: str, prompt: str, usage: GeminiUsage) -> Verdict:
        tools = FileTools(self.root)
        contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
        for _ in range(self.max_turns):
            response = self._generate(instructions, contents, tools)
            usage.add(response)
            calls = response.function_calls
            if not response.candidates or not response.candidates[0].content or not calls:
                raise JudgeNoVerdict(f"{self.model} called no tool:\n{response.model_dump_json()}")
            contents.append(response.candidates[0].content)
            replies: list[types.Part] = []
            for call in calls:
                arguments = call.args or {}
                if call.name == _SUBMIT_VERDICT.name:
                    try:
                        return Verdict.model_validate(arguments)
                    except ValidationError as error:
                        replies.append(_reply(call, f"Error: the verdict is invalid.\n{error}"))
                        continue
                replies.append(_reply(call, tools.call(call.name or "", arguments)))
            contents.append(types.Content(role="user", parts=replies))
        raise JudgeNoVerdict(f"{self.model} returned no verdict in {self.max_turns} turns.")

    def _generate(
        self, instructions: str, contents: list[types.Content], tools: FileTools
    ) -> types.GenerateContentResponse:
        limit = self.request_limit_seconds
        remaining = None
        if self.deadline is not None:
            remaining = self.deadline.remaining_seconds()
            limit = min(limit, remaining)
            if limit <= 0:
                raise self.deadline.reached()
        config = types.GenerateContentConfig(
            system_instruction=instructions,
            tools=[types.Tool(function_declarations=[*tools.declarations, _SUBMIT_VERDICT])],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=types.FunctionCallingConfigMode.ANY
                )
            ),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            # Streamed thought summaries keep bytes flowing while the model thinks, so proxies
            # that drop a response slow to start don't cut long calls off.
            thinking_config=types.ThinkingConfig(include_thoughts=True),
            http_options=types.HttpOptions(
                timeout=int(limit * 1000), retry_options=_retries(remaining)
            ),
        )
        try:
            return _merged(list(self._stream(contents, config, time.monotonic() + limit)))
        except httpx.TimeoutException as error:
            raise self._timed_out() from error
        except errors.APIError as error:
            raise JudgeProcessError(
                f"{self.model} failed with {error.code}: {error.message}"
            ) from error

    def _stream(
        self, contents: list[types.Content], config: types.GenerateContentConfig, until: float
    ) -> Iterator[types.GenerateContentResponse]:
        chunks = self.client.models.generate_content_stream(
            model=self.model, contents=contents, config=config
        )
        for chunk in chunks:
            if time.monotonic() > until:
                raise self._timed_out()
            yield chunk

    def _timed_out(self) -> JudgeTimeout:
        if self.deadline is not None and self.deadline.remaining_seconds() <= 0:
            return self.deadline.reached()
        return JudgeTimeout(f"{self.model} took over {self.request_limit_seconds:g}s to answer.")


def _retries(seconds: float | None) -> types.HttpRetryOptions:
    # The SDK backs off 1s doubling to 60s, plus up to 1s of jitter. With a deadline, retries
    # stop once the backoff would pass it; without one, as in an eval, they run about 6 minutes
    # so a 429 from exhausted shared capacity has time to clear.
    sleeps = accumulate(min(2**retry, 60) + 1 for retry in range(_MAX_ATTEMPTS - 1))
    retries = sum(1 for slept in sleeps if seconds is None or slept <= seconds)
    return types.HttpRetryOptions(attempts=1 + retries)


def _merged(chunks: Sequence[types.GenerateContentResponse]) -> types.GenerateContentResponse:
    candidates = [chunk.candidates[0] for chunk in chunks if chunk.candidates]
    parts = [
        part
        for candidate in candidates
        if candidate.content
        for part in candidate.content.parts or []
        if not part.thought or part.thought_signature
    ]
    usages = [chunk.usage_metadata for chunk in chunks if chunk.usage_metadata]
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=parts),
                finish_reason=candidates[-1].finish_reason,
            )
        ]
        if candidates
        else [],
        usage_metadata=usages[-1] if usages else None,
    )


def _reply(call: types.FunctionCall, result: str) -> types.Part:
    return types.Part(
        function_response=types.FunctionResponse(
            id=call.id, name=call.name, response={"result": result}
        )
    )
