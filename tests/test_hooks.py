import json
import os
import subprocess
import sysconfig
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "codeguard"
STOP_HOOK = PLUGIN / "hooks" / "stop.sh"
STOP_COMMAND = '"${CLAUDE_PLUGIN_ROOT}/hooks/stop.sh"'
SCRIPTS = sysconfig.get_path("scripts")


def commands(config: str, event: str) -> list[str]:
    hooks = json.loads((PLUGIN / "hooks" / config).read_text())["hooks"]
    return [hook["command"] for group in hooks[event] for hook in group["hooks"]]


REVIEW_FAILED = "codeguard review failed, so these changes were not reviewed. Tell the user."
TRACEBACK_HEADING = "Traceback (most recent call last):\n"
BROKEN_RULE_ERROR = (
    "Error: Cannot parse rule {root}/.codeguard/rules/pattern/broken.yml\n"
    "Help: The file is not a valid ast-grep rule. Please refer to doc and fix the error.\n"
    "See also: https://ast-grep.github.io/guide/rule-config.html\n"
    "\n"
    "✖ Caused by\n"
    "╰▻ Fail to parse yaml as RuleConfig\n"
    "╰▻ id: invalid type: sequence, expected a string at line 1 column 5\n"
    "\n"
)


REQUIRED_FIXES = (
    "These errors are required fixes, not suggestions. Fix the code. If the fix needs a "
    "decision, ask the user. Don't change .codeguard/config.yaml to silence them. Leave the "
    "warnings: CI logs them for review, so don't fix them or raise them with the user."
)
ALREADY_REPORTED = "codeguard already reported these errors, so the stop goes through."


@pytest.fixture(autouse=True)
def home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(path))
    return path


def run_stop_hook(
    repo, hook_input: dict, path: str = f"{SCRIPTS}{os.pathsep}{os.environ['PATH']}"
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [STOP_HOOK],
        cwd=repo.root,
        input=json.dumps(hook_input),
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": path},
    )


def stop(session_id: str = "session-1", **fields) -> dict:
    return {"session_id": session_id, "stop_hook_active": False, **fields}


class TestHookConfig:
    def test_claude_code_reviews_when_an_agent_stops(self):
        assert commands("hooks.json", "Stop") == [STOP_COMMAND]

    def test_claude_code_reviews_when_a_subagent_stops(self):
        assert commands("hooks.json", "SubagentStop") == [STOP_COMMAND]

    def test_codex_reviews_when_an_agent_stops(self):
        assert commands("codex.json", "Stop") == [STOP_COMMAND]


class TestStopHook:
    def test_blocking_diagnostic_blocks_the_stop(self, repo, make_diagnostic):
        repo.write("a.py", "print(1)\n")

        result = run_stop_hook(repo, {"stop_hook_active": False})

        assert result.stderr == f"{make_diagnostic()}\n{REQUIRED_FIXES}\n"
        assert result.returncode == 2

    def test_blocks_even_when_the_stop_hook_is_already_active(self, repo):
        repo.write("a.py", "print(1)\n")

        result = run_stop_hook(repo, stop(stop_hook_active=True))

        assert result.returncode == 2

    def test_already_reported_errors_let_the_agent_stop(self, repo, make_diagnostic):
        repo.write("a.py", "print(1)\n")
        run_stop_hook(repo, stop())

        result = run_stop_hook(repo, stop(stop_hook_active=True))

        assert result.stderr == f"{ALREADY_REPORTED}\n{make_diagnostic()}\n"
        assert result.returncode == 1

    def test_new_errors_block_after_earlier_ones_were_reported(self, repo):
        repo.write("a.py", "print(1)\n")
        run_stop_hook(repo, stop())
        repo.write("a.py", "print(1)\nprint(2)\n")

        result = run_stop_hook(repo, stop(stop_hook_active=True))

        assert result.returncode == 2

    def test_errors_reported_to_another_session_block(self, repo):
        repo.write("a.py", "print(1)\n")
        run_stop_hook(repo, stop("session-1"))

        result = run_stop_hook(repo, stop("session-2"))

        assert result.returncode == 2

    def test_errors_reported_to_the_main_agent_block_a_subagent(self, repo):
        repo.write("a.py", "print(1)\n")
        run_stop_hook(repo, stop())

        result = run_stop_hook(repo, stop(agent_id="agent-1"))

        assert result.returncode == 2

    def test_resolved_errors_block_again_when_they_return(self, repo):
        repo.write("a.py", "print(1)\n")
        run_stop_hook(repo, stop())
        repo.write("a.py", "x = 1\n")
        run_stop_hook(repo, stop())
        repo.write("a.py", "print(1)\n")

        result = run_stop_hook(repo, stop())

        assert result.returncode == 2

    def test_reports_without_editing_the_reviewed_file(self, repo):
        repo.write("a.py", "print(1)\n")

        run_stop_hook(repo, {"stop_hook_active": False})

        assert (repo.root / "a.py").read_text() == "print(1)\n"

    def test_no_blocking_diagnostic_lets_the_agent_stop(self, repo):
        repo.write("a.py", "x = 1\n")

        result = run_stop_hook(repo, {"stop_hook_active": False})

        assert result.stderr == ""
        assert result.returncode == 0

    def test_review_error_blocks_the_stop(self, repo):
        repo.write(".codeguard/rules/pattern/broken.yml", "id: [\n")
        repo.write("a.py", "print(1)\n")

        result = run_stop_hook(repo, {"stop_hook_active": False})

        ast_grep_error, traceback = result.stderr.split(TRACEBACK_HEADING)
        assert ast_grep_error == BROKEN_RULE_ERROR.format(root=repo.root)
        assert traceback.splitlines()[-1] == REVIEW_FAILED
        assert result.returncode == 2

    def test_review_error_lets_an_already_blocked_agent_stop(self, repo):
        repo.write(".codeguard/rules/pattern/broken.yml", "id: [\n")
        repo.write("a.py", "print(1)\n")

        result = run_stop_hook(repo, {"stop_hook_active": True})

        ast_grep_error, traceback = result.stderr.split(TRACEBACK_HEADING)
        assert ast_grep_error == BROKEN_RULE_ERROR.format(root=repo.root)
        assert traceback.splitlines()[-1] == REVIEW_FAILED
        assert result.returncode == 1

    def test_missing_codeguard_blocks_the_stop(self, repo):
        result = run_stop_hook(repo, {"stop_hook_active": False}, path="/usr/bin:/bin")

        assert result.stderr == f"codeguard is not on PATH.\n{REVIEW_FAILED}\n"
        assert result.returncode == 2
