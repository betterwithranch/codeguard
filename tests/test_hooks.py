import json
import os
import shutil
import subprocess
import sysconfig
from pathlib import Path

import pytest
from claude_output import fake_claude_script

PLUGIN = Path(__file__).resolve().parent.parent / "plugins" / "codeguard"
SCRIPTS = sysconfig.get_path("scripts")
UV = Path(shutil.which("uv") or "uv")
CLAUDE_CODE_COMMAND = 'uv run --quiet --script "${CLAUDE_PLUGIN_ROOT}/hooks/stop.py" claude-code'
CODEX_COMMAND = 'uv run --quiet --script "${CLAUDE_PLUGIN_ROOT}/hooks/stop.py" codex'
REQUIRED_FIXES = (
    "These errors are required fixes, not suggestions. Fix the code. If the fix needs a "
    "decision, ask the user. Don't change .codeguard/config.yaml to silence them."
)
NOT_REVIEWED = "codeguard review failed, so these changes were not reviewed."
INSTALL = (
    "curl -LsSf https://raw.githubusercontent.com/betterwithranch/codeguard/v0/install.sh | sh"
)


def commands(config: str, event: str) -> list[str]:
    hooks = json.loads((PLUGIN / "hooks" / config).read_text())["hooks"]
    return [hook["command"] for group in hooks[event] for hook in group["hooks"]]


@pytest.fixture(autouse=True)
def home(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(path))
    return path


@pytest.fixture
def uv_only(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A PATH directory with uv and nothing else, so codeguard is not on PATH."""
    path = tmp_path_factory.mktemp("uv-only")
    (path / "uv").symlink_to(UV)
    return path


@pytest.fixture
def claude_bin(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("claude-bin")


def put_claude(bin_dir: Path, script: str) -> None:
    claude = bin_dir / "claude"
    claude.write_text(script)
    claude.chmod(0o755)


def bind_skill(repo, make_skill) -> None:
    repo.write(".claude/skills/placement/SKILL.md", make_skill().text)
    repo.write(
        ".codeguard/bindings/placement.yaml",
        'skill: .claude/skills/placement\npaths: ["**/*.py"]\ntriggers: [any]\n',
    )
    repo.commit("Bind the skill")


def run_stop_hook(
    repo,
    hook_input: dict,
    command: str = CLAUDE_CODE_COMMAND,
    path: list[Path | str] | None = None,
) -> dict:
    """Run a hook config's command and return the one JSON object it must print."""
    directories = path_with() if path is None else path
    result = subprocess.run(
        ["sh", "-c", command],
        cwd=repo.root,
        input=json.dumps(hook_input),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "CLAUDE_PLUGIN_ROOT": str(PLUGIN),
            "PATH": os.pathsep.join(str(directory) for directory in directories),
        },
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def path_with(*first: Path) -> list[Path | str]:
    return [*first, SCRIPTS, UV.parent, "/usr/bin", "/bin"]


def stop(stop_hook_active: bool = False) -> dict:
    return {"session_id": "session-1", "stop_hook_active": stop_hook_active}


class TestHookConfig:
    def test_claude_code_reviews_when_an_agent_stops(self):
        assert commands("hooks.json", "Stop") == [CLAUDE_CODE_COMMAND]

    def test_claude_code_reviews_when_a_subagent_stops(self):
        assert commands("hooks.json", "SubagentStop") == [CLAUDE_CODE_COMMAND]

    def test_codex_reviews_when_an_agent_stops(self):
        assert commands("codex.json", "Stop") == [CODEX_COMMAND]


class TestStopHook:
    def test_blocking_diagnostic_blocks_the_stop(self, repo, make_diagnostic):
        repo.write("a.py", "print(1)\n")

        response = run_stop_hook(repo, stop())

        assert response == {
            "decision": "block",
            "reason": f"{make_diagnostic()}\n{REQUIRED_FIXES}",
        }

    def test_the_same_error_blocks_every_time(self, repo):
        repo.write("a.py", "print(1)\n")
        run_stop_hook(repo, stop())

        response = run_stop_hook(repo, stop(stop_hook_active=True))

        assert response["decision"] == "block"

    def test_configured_warning_goes_to_the_user(self, repo, make_diagnostic):
        repo.write("a.py", "breakpoint()\n")

        response = run_stop_hook(repo, stop())

        assert response == {
            "systemMessage": f"codeguard warnings:\n{make_diagnostic(warning=True)}"
        }

    def test_only_blocking_items_reach_the_agent(self, repo, make_diagnostic):
        repo.write("a.py", "print(1)\nbreakpoint()\n")

        response = run_stop_hook(repo, stop())

        assert response == {
            "decision": "block",
            "reason": f"{make_diagnostic()}\n{REQUIRED_FIXES}",
            "systemMessage": f"codeguard warnings:\n{make_diagnostic(warning=True, line=2)}",
        }

    def test_low_confidence_finding_goes_to_the_user(
        self, repo, claude_bin, make_skill, make_diagnostic
    ):
        bind_skill(repo, make_skill)
        repo.write("a.py", "x = 1\n")
        violation = {"file": "a.py", "line": 1, "message": "Move it."}
        put_claude(claude_bin, fake_claude_script([{**violation, "confidence": 0.4}]))
        finding = make_diagnostic(
            judged=True,
            rule="placement",
            message="Move it.",
            note=None,
            warning=False,
            confidence=0.4,
        ).as_warning()

        response = run_stop_hook(repo, stop(), path=path_with(claude_bin))

        assert response == {"systemMessage": f"codeguard warnings:\n{finding}"}

    def test_judge_error_on_an_error_rule_goes_to_the_user(self, repo, claude_bin, make_skill):
        bind_skill(repo, make_skill)
        repo.write("a.py", "x = 1\n")
        put_claude(claude_bin, "#!/bin/sh\ncat > /dev/null\necho 'rate limited'\nexit 1\n")

        response = run_stop_hook(repo, stop(), path=path_with(claude_bin))

        assert list(response) == ["systemMessage"]
        assert response["systemMessage"].startswith(
            "codeguard warnings:\na.py: warning placement: The judge call failed"
        )

    def test_no_diagnostics_lets_the_agent_stop(self, repo):
        repo.write("a.py", "x = 1\n")

        assert run_stop_hook(repo, stop()) == {}

    def test_reports_without_editing_the_reviewed_file(self, repo):
        repo.write("a.py", "print(1)\n")

        run_stop_hook(repo, stop())

        assert (repo.root / "a.py").read_text() == "print(1)\n"

    def test_crashed_review_goes_to_the_user(self, repo):
        repo.write(".codeguard/rules/pattern/broken.yml", "id: [\n")
        repo.write("a.py", "print(1)\n")

        response = run_stop_hook(repo, stop())

        assert list(response) == ["systemMessage"]
        assert response["systemMessage"].startswith(
            f"{NOT_REVIEWED}\nError: Cannot parse rule {repo.root}/.codeguard/rules/pattern/"
            "broken.yml\n"
        )

    def test_missing_codeguard_goes_to_the_user_with_the_install_command(self, repo, uv_only):
        response = run_stop_hook(repo, stop(), path=[uv_only, "/usr/bin", "/bin"])

        assert response == {
            "systemMessage": "codeguard is not on PATH, so these changes were not reviewed. "
            f"Install it:\n{INSTALL}"
        }

    def test_claude_code_and_codex_get_the_same_response(self, repo):
        repo.write("a.py", "print(1)\nbreakpoint()\n")

        claude_code = run_stop_hook(repo, stop(), CLAUDE_CODE_COMMAND)
        codex = run_stop_hook(repo, {"session_id": "s", "turn_id": "t"}, CODEX_COMMAND)

        assert claude_code == codex
