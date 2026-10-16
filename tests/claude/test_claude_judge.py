import json
from dataclasses import dataclass, field
from pathlib import Path
from threading import Semaphore

import pytest
from claude_output import MODEL_USAGE, fake_claude_script
from spans import finished_span_attributes

from codeguard.claude import ClaudeJudge
from codeguard.review import JudgeError, JudgeRequest, Verdict

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


@dataclass
class RecordingProcesses:
    events: list[str] = field(default_factory=list)

    def __enter__(self) -> None:
        self.events.append("acquired")

    def __exit__(self, *exc_info: object) -> None:
        self.events.append("released")


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

    def test_identity_changes_with_the_model(self, tmp_path, processes):
        sonnet = ClaudeJudge(tmp_path, model="claude-sonnet-5-5", processes=processes)
        opus = ClaudeJudge(tmp_path, model="claude-opus-5-5", processes=processes)

        assert sonnet.identity != opus.identity
