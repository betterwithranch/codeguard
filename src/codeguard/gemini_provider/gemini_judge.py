from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
import logfire
from google.genai import errors, types
from pydantic import ValidationError

from codeguard.gemini_provider.file_tools import FileTools
from codeguard.gemini_provider.gemini_usage import GeminiUsage
from codeguard.review import Deadline, JudgeError, JudgeRequest, Verdict

_PROVIDER = "gemini"
_MAX_TURNS = 25
_SUBMIT_VERDICT = types.FunctionDeclaration(
    name="submit_verdict",
    description="Report the violations in the file under review. Call it once, last.",
    parameters_json_schema=Verdict.model_json_schema(),
)


class GeminiModels(Protocol):
    def generate_content(
        self, *, model: str, contents: list[types.Content], config: types.GenerateContentConfig
    ) -> types.GenerateContentResponse: ...


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
                raise JudgeError(f"{self.model} called no tool:\n{response.model_dump_json()}")
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
        raise JudgeError(f"{self.model} returned no verdict in {self.max_turns} turns.")

    def _generate(
        self, instructions: str, contents: list[types.Content], tools: FileTools
    ) -> types.GenerateContentResponse:
        http_options = None
        if self.deadline is not None:
            remaining = self.deadline.remaining_seconds()
            if remaining <= 0:
                raise self.deadline.reached()
            http_options = types.HttpOptions(timeout=int(remaining * 1000))
        config = types.GenerateContentConfig(
            system_instruction=instructions,
            tools=[types.Tool(function_declarations=[*tools.declarations, _SUBMIT_VERDICT])],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode=types.FunctionCallingConfigMode.ANY
                )
            ),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            http_options=http_options,
        )
        try:
            return self.client.models.generate_content(
                model=self.model, contents=contents, config=config
            )
        except httpx.TimeoutException as error:
            if self.deadline is None:
                raise JudgeError(f"{self.model} timed out: {error}") from error
            raise self.deadline.reached() from error
        except errors.APIError as error:
            raise JudgeError(f"{self.model} failed with {error.code}: {error.message}") from error


def _reply(call: types.FunctionCall, result: str) -> types.Part:
    return types.Part(
        function_response=types.FunctionResponse(
            id=call.id, name=call.name, response={"result": result}
        )
    )
