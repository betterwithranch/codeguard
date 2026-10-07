import json
import subprocess
import sysconfig
from pathlib import Path

CODEGUARD = Path(sysconfig.get_path("scripts")) / "codeguard"
NO_PRINT_TEST = ".codeguard/rule-tests/pattern/no-print-test.yml"
NO_PRINT_SNAPSHOT = ".codeguard/rule-tests/pattern/__snapshots__/no-print-snapshot.yml"


class TestReviewCommand:
    def test_error_finding_prints_and_exits_1(self, repo, make_finding):
        repo.write("a.py", "print(1)\n")
        finding = make_finding()

        result = subprocess.run(
            [CODEGUARD, "review"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == (
            f"a.py:1: error no-print: Use logging, not print. [{finding.id}]\n"
            "  print bypasses log levels.\n"
            "  Call logger.info instead.\n"
        )
        assert result.stderr == ""
        assert result.returncode == 1

    def test_warning_finding_prints_and_exits_0(self, repo, make_finding):
        repo.write("a.py", "breakpoint()\n")
        finding = make_finding(warning=True)

        result = subprocess.run(
            [CODEGUARD, "review"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == f"a.py:1: warning no-breakpoint: Remove breakpoint(). [{finding.id}]\n"
        assert result.returncode == 0

    def test_base_reviews_committed_changes(self, repo, make_finding):
        repo.git("switch", "--create", "feature")
        repo.write("a.py", "print(1)\n")
        repo.commit("Add a")
        finding = make_finding()

        result = subprocess.run(
            [CODEGUARD, "review", "--base", "main"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == (
            f"a.py:1: error no-print: Use logging, not print. [{finding.id}]\n"
            "  print bypasses log levels.\n"
            "  Call logger.info instead.\n"
        )
        assert result.returncode == 1

    def test_all_reviews_committed_unchanged_files(self, repo, make_finding):
        repo.write("a.py", "print(1)\n")
        repo.commit("Add a")
        finding = make_finding()

        result = subprocess.run(
            [CODEGUARD, "review", "--all"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == (
            f"a.py:1: error no-print: Use logging, not print. [{finding.id}]\n"
            "  print bypasses log levels.\n"
            "  Call logger.info instead.\n"
        )
        assert result.returncode == 1

    def test_invalid_rule_prints_ast_grep_error(self, repo):
        repo.write(".codeguard/rules/pattern/broken.yml", "id: [\n")
        repo.write("a.py", "print(1)\n")

        result = subprocess.run(
            [CODEGUARD, "review"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stderr.splitlines()[0] == (
            f"Error: Cannot parse rule {repo.root}/.codeguard/rules/pattern/broken.yml"
        )
        assert result.returncode == 1


class TestHookStopCommand:
    def test_error_finding_prints_to_stderr_and_exits_2(self, repo, make_finding):
        repo.write("a.py", "print(1)\n")
        finding = make_finding()
        payload = json.dumps({"cwd": str(repo.root), "permission_mode": "default"})

        result = subprocess.run(
            [CODEGUARD, "hook", "stop"], input=payload, capture_output=True, text=True
        )

        assert result.stderr == (
            f"a.py:1: error no-print: Use logging, not print. [{finding.id}]\n"
            "  print bypasses log levels.\n"
            "  Call logger.info instead.\n"
        )
        assert result.returncode == 2


class TestTestCommand:
    def test_passing_rule_tests_exit_0(self, repo):
        repo.write(NO_PRINT_TEST, "id: no-print\nvalid:\n  - logging.info(1)\n")

        result = subprocess.run([CODEGUARD, "test"], cwd=repo.root, capture_output=True)

        assert result.returncode == 0

    def test_stale_snapshot_entry_fails(self, repo):
        repo.write(
            NO_PRINT_TEST,
            "id: no-print\ninvalid:\n  - print(1)\n  - print(2)\n",
        )
        subprocess.run([CODEGUARD, "test", "--update-all"], cwd=repo.root, check=True)
        repo.write(NO_PRINT_TEST, "id: no-print\ninvalid:\n  - print(2)\n")

        result = subprocess.run(
            [CODEGUARD, "test"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stderr == (
            ".codeguard/rule-tests/pattern/__snapshots__/no-print-snapshot.yml: stale snapshot "
            "entries for no-print. Run codeguard test --update-all.\n"
        )
        assert result.returncode == 1

    def test_update_all_removes_snapshots_of_removed_tests(self, repo):
        repo.write(NO_PRINT_TEST, "id: no-print\ninvalid:\n  - print(1)\n")
        subprocess.run([CODEGUARD, "test", "--update-all"], cwd=repo.root, check=True)
        (repo.root / NO_PRINT_TEST).unlink()

        subprocess.run([CODEGUARD, "test", "--update-all"], cwd=repo.root, check=True)

        assert not (repo.root / NO_PRINT_SNAPSHOT).exists()

    def test_failing_rule_tests_exit_1(self, repo):
        repo.write(NO_PRINT_TEST, "id: no-print\nvalid:\n  - print(1)\n")

        result = subprocess.run([CODEGUARD, "test"], cwd=repo.root, capture_output=True)

        assert result.returncode == 1
