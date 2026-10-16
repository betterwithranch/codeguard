import json
from pathlib import Path

import pytest

from codeguard.claude import ClaudeJudge
from codeguard.review import Confidence, JudgeRequest, Verdict


@pytest.fixture
def arguments(tmp_path) -> Path:
    return tmp_path / "arguments"


@pytest.fixture
def fake_claude_executable(tmp_path, arguments) -> str:
    output = {
        "structured_output": {
            "violations": [
                {
                    "file": "a.py",
                    "line": 1,
                    "message": "Move it.",
                    "note": "Call logger.info instead.",
                    "confidence": "low",
                }
            ]
        }
    }
    executable = tmp_path / "claude"
    executable.write_text(
        "#!/bin/sh\n"
        f'echo "$@" > {arguments}\n'
        "cat > /dev/null\n"
        f"echo '{json.dumps(output)}'\n"
    )
    executable.chmod(0o755)
    return str(executable)


class TestClaudeJudge:
    def test_verdict_comes_from_claude_structured_output(
        self, tmp_path, fake_claude_executable, make_skill, make_violation
    ):
        judge = ClaudeJudge(tmp_path, executable=fake_claude_executable)

        verdict = judge.judge(JudgeRequest(make_skill(), "a.py"))

        assert verdict == Verdict(
            violations=(make_violation(message="Move it.", confidence=Confidence.LOW),)
        )

    def test_claude_runs_the_given_model(
        self, tmp_path, fake_claude_executable, arguments, make_skill
    ):
        judge = ClaudeJudge(tmp_path, model="claude-opus-5-5", executable=fake_claude_executable)

        judge.judge(JudgeRequest(make_skill(), "a.py"))

        assert "--model claude-opus-5-5" in arguments.read_text()

    def test_claude_has_only_read_only_tools(
        self, tmp_path, fake_claude_executable, arguments, make_skill
    ):
        judge = ClaudeJudge(tmp_path, executable=fake_claude_executable)

        judge.judge(JudgeRequest(make_skill(), "a.py"))

        assert "--tools Read,Grep,Glob" in arguments.read_text()

    def test_identity_changes_with_the_model(self, tmp_path):
        sonnet = ClaudeJudge(tmp_path, model="claude-sonnet-5-5")
        opus = ClaudeJudge(tmp_path, model="claude-opus-5-5")

        assert sonnet.identity != opus.identity
