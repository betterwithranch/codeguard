import time
from dataclasses import dataclass, field

import httpx
import pytest
from google.genai import errors, types
from spans import finished_span_attributes

from codeguard.gemini_provider import GeminiJudge
from codeguard.review import Deadline, JudgeError, JudgeRequest, Verdict

MODEL = "gemini-3.8-flash"
VIOLATION = {
    "file": "a.py",
    "line": 1,
    "message": "Move it.",
    "note": "Call logger.info instead.",
    "confidence": 0.4,
}


def call(name: str, **args: object) -> types.Part:
    return types.Part(function_call=types.FunctionCall(id=f"{name}-id", name=name, args=args))


def response(*parts: types.Part, prompt_tokens: int = 10) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=list(parts)))],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=prompt_tokens,
            candidates_token_count=3,
            cached_content_token_count=4,
            thoughts_token_count=5,
        ),
    )


@dataclass
class ScriptedClient:
    responses: list[types.GenerateContentResponse]
    requests: list[tuple[str, list[types.Content], types.GenerateContentConfig]] = field(
        default_factory=list
    )

    def generate_content(
        self, *, model: str, contents: list[types.Content], config: types.GenerateContentConfig
    ) -> types.GenerateContentResponse:
        self.requests.append((model, list(contents), config))
        return self.responses.pop(0)

    @property
    def models(self) -> "ScriptedClient":
        return self


@dataclass
class FailingClient:
    error: Exception

    def generate_content(
        self, *, model: str, contents: list[types.Content], config: types.GenerateContentConfig
    ) -> types.GenerateContentResponse:
        raise self.error

    @property
    def models(self) -> "FailingClient":
        return self


@dataclass
class RecordingProcesses:
    events: list[str] = field(default_factory=list)

    def __enter__(self) -> None:
        self.events.append("acquired")

    def __exit__(self, *exc_info: object) -> None:
        self.events.append("released")


@pytest.fixture(autouse=True)
def reviewed_file(tmp_path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n")
    (tmp_path / "logger.py").write_text("def info(message): ...\n")


def judge_with(tmp_path, models, **kwargs) -> GeminiJudge:
    return GeminiJudge(tmp_path, MODEL, models, RecordingProcesses(), **kwargs)


def tool_replies(contents: list[types.Content]) -> list[object]:
    return [
        part.function_response.response["result"]
        for part in contents[-1].parts or []
        if part.function_response and part.function_response.response
    ]


class TestGeminiJudge:
    def test_verdict_comes_from_the_submitted_verdict(self, tmp_path, make_skill):
        models = ScriptedClient([response(call("submit_verdict", violations=[VIOLATION]))])

        verdict = judge_with(tmp_path, models).judge(JudgeRequest(make_skill(), "a.py"))

        assert verdict == Verdict.model_validate({"violations": [VIOLATION]})

    def test_sends_the_instructions_and_the_skill(self, tmp_path, make_skill):
        models = ScriptedClient([response(call("submit_verdict", violations=[]))])
        request = JudgeRequest(make_skill(), "a.py")

        judge_with(tmp_path, models).judge(request)

        model, contents, config = models.requests[0]
        assert model == MODEL
        assert config.system_instruction == request.instructions("print(1)\n")
        assert [part.text for part in contents[0].parts or []] == [make_skill().text]

    def test_requires_a_tool_call_on_every_turn(self, tmp_path, make_skill):
        models = ScriptedClient([response(call("submit_verdict", violations=[]))])

        judge_with(tmp_path, models).judge(JudgeRequest(make_skill(), "a.py"))

        tool_config = models.requests[0][2].tool_config
        assert tool_config and tool_config.function_calling_config
        assert tool_config.function_calling_config.mode == types.FunctionCallingConfigMode.ANY

    def test_answers_file_tool_calls_before_the_verdict(self, tmp_path, make_skill):
        models = ScriptedClient(
            [
                response(call("read_file", path="logger.py")),
                response(call("submit_verdict", violations=[])),
            ]
        )

        judge_with(tmp_path, models).judge(JudgeRequest(make_skill(), "a.py"))

        assert tool_replies(models.requests[1][1]) == ["     1\tdef info(message): ...\n"]

    def test_keeps_the_model_turn_in_the_conversation(self, tmp_path, make_skill):
        read = response(call("read_file", path="logger.py"))
        models = ScriptedClient([read, response(call("submit_verdict", violations=[]))])

        judge_with(tmp_path, models).judge(JudgeRequest(make_skill(), "a.py"))

        assert read.candidates
        assert models.requests[1][1][1] == read.candidates[0].content

    def test_invalid_verdict_is_sent_back_to_correct(self, tmp_path, make_skill):
        models = ScriptedClient(
            [
                response(call("submit_verdict", violations=[{"file": "a.py"}])),
                response(call("submit_verdict", violations=[])),
            ]
        )

        verdict = judge_with(tmp_path, models).judge(JudgeRequest(make_skill(), "a.py"))

        assert verdict == Verdict(violations=())
        [reply] = tool_replies(models.requests[1][1])
        assert str(reply).startswith("Error: the verdict is invalid.")

    def test_response_without_a_tool_call_is_a_judge_error(self, tmp_path, make_skill):
        models = ScriptedClient([response(types.Part.from_text(text="It looks fine."))])

        with pytest.raises(JudgeError, match=f"^{MODEL} called no tool"):
            judge_with(tmp_path, models).judge(JudgeRequest(make_skill(), "a.py"))

    def test_no_verdict_within_the_turn_limit_is_a_judge_error(self, tmp_path, make_skill):
        models = ScriptedClient([response(call("glob", pattern="*.py")) for _ in range(2)])

        with pytest.raises(JudgeError, match=f"^{MODEL} returned no verdict in 2 turns.$"):
            judge_with(tmp_path, models, max_turns=2).judge(JudgeRequest(make_skill(), "a.py"))

    def test_api_error_is_a_judge_error(self, tmp_path, make_skill):
        error = errors.ClientError(429, {"error": {"message": "Quota exceeded."}})

        with pytest.raises(JudgeError, match=f"^{MODEL} failed with 429: Quota exceeded.$"):
            judge_with(tmp_path, FailingClient(error)).judge(JudgeRequest(make_skill(), "a.py"))

    def test_call_after_the_deadline_is_a_judge_error_without_calling_gemini(
        self, tmp_path, make_skill
    ):
        models = ScriptedClient([])
        deadline = Deadline(minutes=1, started=time.monotonic() - 60)

        with pytest.raises(JudgeError, match="^The review reached its 1-minute time limit.$"):
            judge_with(tmp_path, models, deadline=deadline).judge(
                JudgeRequest(make_skill(), "a.py")
            )
        assert models.requests == []

    def test_request_times_out_at_the_deadline(self, tmp_path, make_skill):
        models = ScriptedClient([response(call("submit_verdict", violations=[]))])
        deadline = Deadline(minutes=1, started=time.monotonic() - 30)

        judge_with(tmp_path, models, deadline=deadline).judge(JudgeRequest(make_skill(), "a.py"))

        http_options = models.requests[0][2].http_options
        assert http_options and http_options.timeout
        assert 29_000 < http_options.timeout <= 30_000

    def test_timeout_is_the_time_limit_error(self, tmp_path, make_skill):
        models = FailingClient(httpx.ReadTimeout("timed out"))
        deadline = Deadline(minutes=1)

        with pytest.raises(JudgeError, match="^The review reached its 1-minute time limit.$"):
            judge_with(tmp_path, models, deadline=deadline).judge(
                JudgeRequest(make_skill(), "a.py")
            )

    def test_each_call_holds_a_process_slot(self, tmp_path, make_skill):
        processes = RecordingProcesses()
        models = ScriptedClient([response(call("submit_verdict", violations=[]))])

        GeminiJudge(tmp_path, MODEL, models, processes).judge(JudgeRequest(make_skill(), "a.py"))

        assert processes.events == ["acquired", "released"]

    def test_identity_names_the_provider_and_model(self, tmp_path):
        assert judge_with(tmp_path, ScriptedClient([])).identity == f"gemini\0{MODEL}"

    def test_call_records_its_usage_across_turns(self, tmp_path, make_skill, capfire):
        models = ScriptedClient(
            [
                response(call("glob", pattern="*.py"), prompt_tokens=10),
                response(call("submit_verdict", violations=[]), prompt_tokens=20),
            ]
        )

        judge_with(tmp_path, models).judge(JudgeRequest(make_skill(), "a.py"))

        assert finished_span_attributes(capfire, "gemini judges {rule} on {file}") == [
            {
                "rule": make_skill().name,
                "file": "a.py",
                "model": MODEL,
                "num_turns": 2,
                "input_tokens": 30,
                "output_tokens": 6,
                "cache_read_input_tokens": 8,
                "thinking_tokens": 10,
            }
        ]
