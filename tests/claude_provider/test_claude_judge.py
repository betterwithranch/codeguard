import json
import time
from collections.abc import Hashable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import Semaphore

import pytest
from claude_output import MODEL_USAGE, fake_claude_script
from spans import finished_span_attributes

from codeguard.claude_provider import ClaudeJudge, PromptCacheWarmup
from codeguard.review import Deadline, JudgeError, JudgeRequest, Verdict

MODEL = "claude-sonnet-5-5"


@pytest.fixture
def arguments(tmp_path) -> Path:
    return tmp_path / "arguments"


@pytest.fixture
def fake_claude_executable(tmp_path, arguments) -> str:
    script = fake_claude_script(
        [
            {
                "file": "a.py",
                "line": 1,
                "message": "Move it.",
                "note": "Call logger.info instead.",
                "confidence": 0.4,
            }
        ],
        before=f'echo "$@" > {arguments}\n',
    )
    executable = tmp_path / "claude"
    executable.write_text(script)
    executable.chmod(0o755)
    return str(executable)


@pytest.fixture(autouse=True)
def reviewed_file(tmp_path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n")


@pytest.fixture
def prompt(tmp_path) -> Path:
    return tmp_path / "prompt"


@pytest.fixture
def prompt_recording_claude_executable(tmp_path, prompt) -> str:
    executable = tmp_path / "claude"
    executable.write_text(fake_claude_script([], before=f"cat > {prompt}\n"))
    executable.chmod(0o755)
    return str(executable)


@pytest.fixture
def processes() -> Semaphore:
    return Semaphore(1)


@pytest.fixture
def failing_claude_executable(tmp_path) -> str:
    executable = tmp_path / "claude"
    executable.write_text(
        "#!/bin/sh\ncat > /dev/null\necho 'rate limited'\necho 'try later' >&2\nexit 1\n"
    )
    executable.chmod(0o755)
    return str(executable)


@pytest.fixture
def hanging_claude_executable(tmp_path) -> str:
    executable = tmp_path / "claude"
    executable.write_text("#!/bin/sh\nsleep 10\n")
    executable.chmod(0o755)
    return str(executable)


def deadline_in(seconds: float) -> Deadline:
    return Deadline(minutes=1, started=time.monotonic() - 60 + seconds)


@dataclass
class RecordingProcesses:
    events: list[str] = field(default_factory=list)

    def __enter__(self) -> None:
        self.events.append("acquired")

    def __exit__(self, *exc_info: object) -> None:
        self.events.append("released")


@dataclass
class RecordingWarmup(PromptCacheWarmup):
    prefixes: list[Hashable] = field(default_factory=list)

    @contextmanager
    def after_first_call(self, prefix: Hashable) -> Iterator[None]:
        self.prefixes.append(prefix)
        with super().after_first_call(prefix):
            yield


class TestClaudeJudge:
    def test_call_records_its_usage(
        self, tmp_path, processes, fake_claude_executable, make_skill, capfire
    ):
        judge = ClaudeJudge(tmp_path, MODEL, processes, fake_claude_executable)

        judge.judge(JudgeRequest(make_skill(), "a.py"))

        assert finished_span_attributes(capfire, "claude judges {rule} on {file}") == [
            {
                "rule": make_skill().name,
                "file": "a.py",
                "model": MODEL,
                "returncode": 0,
                "is_error": False,
                "subtype": "success",
                "num_turns": 3,
                "duration_ms": 2036,
                "duration_api_ms": 1901,
                "cost_usd": 0.0022,
                "input_tokens": MODEL_USAGE["inputTokens"],
                "output_tokens": MODEL_USAGE["outputTokens"],
                "cache_read_input_tokens": MODEL_USAGE["cacheReadInputTokens"],
                "cache_creation_input_tokens": MODEL_USAGE["cacheCreationInputTokens"],
                "thinking_tokens": MODEL_USAGE["thinkingTokens"],
                "model_usage": json.dumps(
                    {
                        MODEL: {
                            "input_tokens": MODEL_USAGE["inputTokens"],
                            "output_tokens": MODEL_USAGE["outputTokens"],
                            "cache_read_input_tokens": MODEL_USAGE["cacheReadInputTokens"],
                            "cache_creation_input_tokens": MODEL_USAGE["cacheCreationInputTokens"],
                            "thinking_tokens": MODEL_USAGE["thinkingTokens"],
                            "cost_usd": MODEL_USAGE["costUSD"],
                        }
                    },
                    separators=(",", ":"),
                ),
                "five_hour_utilization": 0.16,
                "seven_day_utilization": 0.11,
            }
        ]

    def test_failed_call_is_a_judge_error_with_claude_output(
        self, tmp_path, processes, failing_claude_executable, make_skill
    ):
        judge = ClaudeJudge(tmp_path, MODEL, processes, failing_claude_executable)

        with pytest.raises(JudgeError) as error:
            judge.judge(JudgeRequest(make_skill(), "a.py"))

        assert str(error.value) == (
            f"{failing_claude_executable} exited with 1.\n"
            "stdout:\nrate limited\n\nstderr:\ntry later\n"
        )

    def test_call_after_the_deadline_is_a_judge_error_without_running_claude(
        self, tmp_path, processes, fake_claude_executable, arguments, make_skill
    ):
        judge = ClaudeJudge(
            tmp_path, MODEL, processes, fake_claude_executable, deadline=deadline_in(0)
        )

        with pytest.raises(JudgeError, match="^The review reached its 1-minute time limit.$"):
            judge.judge(JudgeRequest(make_skill(), "a.py"))
        assert not arguments.exists()

    def test_call_running_past_the_deadline_is_a_judge_error(
        self, tmp_path, processes, hanging_claude_executable, make_skill
    ):
        judge = ClaudeJudge(
            tmp_path, MODEL, processes, hanging_claude_executable, deadline=deadline_in(0.5)
        )

        with pytest.raises(JudgeError, match="^The review reached its 1-minute time limit.$"):
            judge.judge(JudgeRequest(make_skill(), "a.py"))

    def test_each_call_holds_a_process_slot(self, tmp_path, fake_claude_executable, make_skill):
        processes = RecordingProcesses()
        judge = ClaudeJudge(tmp_path, MODEL, processes, fake_claude_executable)

        judge.judge(JudgeRequest(make_skill(), "a.py"))

        assert processes.events == ["acquired", "released"]

    def test_verdict_comes_from_claude_structured_output(
        self, tmp_path, processes, fake_claude_executable, make_skill, make_violation
    ):
        judge = ClaudeJudge(tmp_path, MODEL, processes, fake_claude_executable)

        verdict = judge.judge(JudgeRequest(make_skill(), "a.py"))

        assert verdict == Verdict(violations=(make_violation(message="Move it.", confidence=0.4),))

    def test_claude_runs_the_given_model(
        self, tmp_path, processes, fake_claude_executable, arguments, make_skill
    ):
        judge = ClaudeJudge(
            tmp_path,
            model="claude-opus-5-5",
            processes=processes,
            executable=fake_claude_executable,
        )

        judge.judge(JudgeRequest(make_skill(), "a.py"))

        assert "--model claude-opus-5-5" in arguments.read_text()

    def test_claude_has_only_read_only_tools(
        self, tmp_path, processes, fake_claude_executable, arguments, make_skill
    ):
        judge = ClaudeJudge(tmp_path, MODEL, processes, fake_claude_executable)

        judge.judge(JudgeRequest(make_skill(), "a.py"))

        assert "--tools Read,Grep,Glob" in arguments.read_text()

    def test_claude_gets_the_skill_as_the_prompt(
        self, tmp_path, processes, prompt_recording_claude_executable, prompt, make_skill
    ):
        judge = ClaudeJudge(tmp_path, MODEL, processes, prompt_recording_claude_executable)
        request = JudgeRequest(make_skill(), "a.py")

        judge.judge(request)

        assert prompt.read_text() == request.prompt

    def test_claude_gets_the_file_in_the_system_prompt(
        self, tmp_path, processes, fake_claude_executable, arguments, make_skill
    ):
        judge = ClaudeJudge(tmp_path, MODEL, processes, fake_claude_executable)
        request = JudgeRequest(make_skill(), "a.py")

        judge.judge(request)

        assert f"--system-prompt {request.instructions('print(1)\n')}" in arguments.read_text()

    def test_calls_wait_for_the_first_call_with_their_prefix(
        self, tmp_path, processes, fake_claude_executable, make_skill
    ):
        warmup = RecordingWarmup()
        judge = ClaudeJudge(tmp_path, MODEL, processes, fake_claude_executable, warmup)
        request = JudgeRequest(make_skill(), "a.py")

        judge.judge(request)

        assert warmup.prefixes == [(MODEL, request.instructions("print(1)\n"))]

    def test_identity_changes_with_the_model(self, tmp_path, processes):
        sonnet = ClaudeJudge(tmp_path, model="claude-sonnet-5-5", processes=processes)
        opus = ClaudeJudge(tmp_path, model="claude-opus-5-5", processes=processes)

        assert sonnet.identity != opus.identity
