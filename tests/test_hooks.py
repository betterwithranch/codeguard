import json
import os
import subprocess
import sysconfig
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "codeguard"
STOP_HOOK = PLUGIN / "hooks" / "stop.sh"
STOP_COMMAND = '"${CLAUDE_PLUGIN_ROOT}/hooks/stop.sh"'
SCRIPTS = sysconfig.get_path("scripts")


def commands(config: str, event: str) -> list[str]:
    hooks = json.loads((PLUGIN / "hooks" / config).read_text())["hooks"]
    return [hook["command"] for group in hooks[event] for hook in group["hooks"]]


def run_stop_hook(repo, hook_input: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [STOP_HOOK],
        cwd=repo.root,
        input=json.dumps(hook_input),
        capture_output=True,
        text=True,
        env={**os.environ, "PATH": f"{SCRIPTS}{os.pathsep}{os.environ['PATH']}"},
    )


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

        assert result.stderr == f"{make_diagnostic()}\n"
        assert result.returncode == 2

    def test_blocks_even_when_the_stop_hook_is_already_active(self, repo):
        repo.write("a.py", "print(1)\n")

        result = run_stop_hook(repo, {"stop_hook_active": True})

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

    def test_review_error_is_reported_without_blocking(self, repo):
        repo.write(".codeguard/rules/pattern/broken.yml", "id: [\n")
        repo.write("a.py", "print(1)\n")

        result = run_stop_hook(repo, {"stop_hook_active": False})

        assert "Cannot parse rule" in result.stderr
        assert result.returncode == 1
