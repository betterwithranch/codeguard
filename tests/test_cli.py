import json
import os
import subprocess
import sysconfig
from importlib import metadata
from pathlib import Path

from git_repo import GitRepo
from rules_package import write_package

CODEGUARD = Path(sysconfig.get_path("scripts")) / "codeguard"
BUNDLED_AST_GREP = metadata.version("ast-grep-cli")
NO_PRINT_TEST = ".codeguard/rule-tests/pattern/no-print-test.yml"
NO_PRINT_SNAPSHOT = ".codeguard/rule-tests/pattern/__snapshots__/no-print-snapshot.yml"
TRACEBACK_HEADING = "Traceback (most recent call last):\n"
PASSING_NO_PRINT_TEST_REPORT = (
    "Running 1 tests\n"
    "\n"
    "----------- Case Details -----------\n"
    "PASS no-print  .\n"
    "\n"
    "test result: ok. 1 passed; 0 failed;\n"
)


class TestReviewCommand:
    def test_error_diagnostic_prints_and_exits_1(self, repo, make_diagnostic):
        repo.write("a.py", "print(1)\n")
        diagnostic = make_diagnostic()

        result = subprocess.run(
            [CODEGUARD, "review"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == (
            f"a.py:1: error no-print: Use logging, not print. [{diagnostic.id}]\n"
            "  print bypasses log levels.\n"
            "  Call logger.info instead.\n"
        )
        assert result.stderr == ""
        assert result.returncode == 1

    def test_warning_diagnostic_prints_and_exits_0(self, repo, make_diagnostic):
        repo.write("a.py", "breakpoint()\n")
        diagnostic = make_diagnostic(warning=True)

        result = subprocess.run(
            [CODEGUARD, "review"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == (
            f"a.py:1: warning no-breakpoint: Remove breakpoint(). [{diagnostic.id}]\n"
        )
        assert result.stderr == ""
        assert result.returncode == 0

    def test_base_reviews_committed_changes(self, repo, make_diagnostic):
        repo.git("switch", "--create", "feature")
        repo.write("a.py", "print(1)\n")
        repo.commit("Add a")
        diagnostic = make_diagnostic()

        result = subprocess.run(
            [CODEGUARD, "review", "--base", "main"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == (
            f"a.py:1: error no-print: Use logging, not print. [{diagnostic.id}]\n"
            "  print bypasses log levels.\n"
            "  Call logger.info instead.\n"
        )
        assert result.returncode == 1

    def test_all_reviews_committed_unchanged_files(self, repo, make_diagnostic):
        repo.write("a.py", "print(1)\n")
        repo.commit("Add a")
        diagnostic = make_diagnostic()

        result = subprocess.run(
            [CODEGUARD, "review", "--all"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == (
            f"a.py:1: error no-print: Use logging, not print. [{diagnostic.id}]\n"
            "  print bypasses log levels.\n"
            "  Call logger.info instead.\n"
        )
        assert result.returncode == 1

    def test_violation_on_an_unchanged_line_is_not_reported(self, repo):
        repo.write("a.py", "print(1)\n")
        repo.commit("Add a")
        repo.write("a.py", "print(1)\nx = 1\n")

        result = subprocess.run(
            [CODEGUARD, "review"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == ""
        assert result.returncode == 0

    def test_violation_in_an_unchanged_file_is_not_reported(self, repo):
        repo.write("a.py", "print(1)\n")
        repo.commit("Add a")
        repo.write("b.py", "x = 1\n")

        result = subprocess.run(
            [CODEGUARD, "review"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == ""
        assert result.returncode == 0

    def test_invalid_rule_prints_ast_grep_error(self, repo):
        repo.write(".codeguard/rules/pattern/broken.yml", "id: [\n")
        repo.write("a.py", "print(1)\n")

        result = subprocess.run(
            [CODEGUARD, "review"], cwd=repo.root, capture_output=True, text=True
        )

        ast_grep_error, traceback = result.stderr.split(TRACEBACK_HEADING)
        assert result.stdout == ""
        assert ast_grep_error == (
            f"Error: Cannot parse rule {repo.root}/.codeguard/rules/pattern/broken.yml\n"
            "Help: The file is not a valid ast-grep rule. Please refer to doc and fix the error.\n"
            "See also: https://ast-grep.github.io/guide/rule-config.html\n"
            "\n"
            "✖ Caused by\n"
            "╰▻ Fail to parse yaml as RuleConfig\n"
            "╰▻ id: invalid type: sequence, expected a string at line 1 column 5\n"
            "\n"
        )
        assert traceback.endswith("returned non-zero exit status 8.\n")
        assert result.returncode == 2

    def test_outside_a_working_tree_exits_2(self, tmp_path):
        result = subprocess.run([CODEGUARD, "review"], cwd=tmp_path, capture_output=True, text=True)

        git_error, traceback = result.stderr.split(TRACEBACK_HEADING)
        assert result.stdout == ""
        assert git_error == "fatal: not a git repository (or any of the parent directories): .git\n"
        assert traceback.endswith("returned non-zero exit status 128.\n")
        assert result.returncode == 2


class TestReviewWithAstGrepVersion:
    def test_pinned_ast_grep_runs_the_rules(self, repo, make_diagnostic):
        repo.write(".codeguard/config.yaml", f"ast-grep: {BUNDLED_AST_GREP}\n")
        repo.write("a.py", "print(1)\n")

        result = subprocess.run(
            [CODEGUARD, "review"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == f"{make_diagnostic()}\n"
        assert result.returncode == 1

    def test_ast_grep_outside_a_package_range_exits_2(self, repo):
        write_package(repo, prefix="rules/")
        repo.write(
            "rules/codeguard-package.yaml",
            "name: example\nrulesets: [python]\nast-grep: '<0.45'\n",
        )
        repo.write(
            ".codeguard/config.yaml",
            "packages:\n  - path: rules\n    rulesets:\n      python: {}\n",
        )
        repo.write("a.py", "print(1)\n")

        result = subprocess.run(
            [CODEGUARD, "review"], cwd=repo.root, capture_output=True, text=True
        )

        _, traceback = result.stderr.split(TRACEBACK_HEADING)
        assert traceback.splitlines()[-2:] == [
            f"codeguard.config.config_error.ConfigError: {repo.root}/.codeguard is invalid:",
            f"  packages.0: example supports ast-grep <0.45, not {BUNDLED_AST_GREP}",
        ]
        assert result.returncode == 2


class TestReviewWithPackages:
    def test_opted_in_rule_reports_with_its_full_id(self, repo, make_diagnostic):
        write_package(repo, prefix="rules/")
        repo.write(
            ".codeguard/config.yaml",
            "packages:\n"
            "  - path: rules\n"
            "    rulesets:\n"
            "      python:\n"
            "        exclude: [responsibility-placement]\n",
        )
        repo.write("a.py", "x = 1\n")
        repo.commit("Opt in")
        repo.write("a.py", "x = 1\nprint(x)\n")
        local = make_diagnostic(line=2)
        packaged = make_diagnostic(line=2, rule="example/python/no-print", note=None)

        result = subprocess.run(
            [CODEGUARD, "review"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == f"{local}\n{packaged}\n"
        assert result.returncode == 1

    def test_excluded_rule_reports_nothing(self, repo):
        write_package(repo, prefix="rules/")
        repo.write(
            ".codeguard/config.yaml",
            "packages:\n"
            "  - path: rules\n"
            "    rulesets:\n"
            "      python:\n"
            "        exclude: [no-print, responsibility-placement]\n",
        )
        (repo.root / ".codeguard/rules/pattern/no-print.yml").unlink()
        repo.write("a.py", "print(1)\n")

        result = subprocess.run(
            [CODEGUARD, "review"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == ""
        assert result.returncode == 0

    def test_unknown_excluded_rule_exits_2(self, repo):
        write_package(repo, prefix="rules/")
        repo.write(
            ".codeguard/config.yaml",
            "packages:\n"
            "  - path: rules\n"
            "    rulesets:\n"
            "      python:\n"
            "        exclude: [no-prnt]\n",
        )
        repo.write("a.py", "print(1)\n")

        result = subprocess.run(
            [CODEGUARD, "review"], cwd=repo.root, capture_output=True, text=True
        )

        _, traceback = result.stderr.split(TRACEBACK_HEADING)
        assert traceback.splitlines()[-2:] == [
            f"codeguard.config.config_error.ConfigError: {repo.root}/.codeguard is invalid:",
            "  packages.0.rulesets.python: unknown rule no-prnt",
        ]
        assert result.returncode == 2


class TestUpdateCommand:
    def test_prints_each_moved_ref(self, repo, tmp_path_factory):
        remote = GitRepo.init(tmp_path_factory.mktemp("remote").resolve())
        remote.git("tag", "v2.0.0")
        url = f"file://{remote.root}"
        repo.write(
            ".codeguard/config.yaml",
            f"packages:\n  - git: {url}\n    ref: v1.0.0\n    rulesets:\n      python: {{}}\n",
        )

        result = subprocess.run(
            [CODEGUARD, "update"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == f"{url}: v1.0.0 -> v2.0.0\n"
        assert result.stderr == ""
        assert result.returncode == 0


class TestEvalCommand:
    def test_package_repo_evaluates_judge_rules(self, tmp_path, tmp_path_factory):
        package = GitRepo.init(tmp_path_factory.mktemp("package").resolve())
        write_package(package)
        package.write(
            "python/rule-evals/responsibility-placement-eval.yml",
            "id: responsibility-placement\ninvalid: [invoice.py]\n",
        )
        package.write("python/rule-evals/responsibility-placement/invoice.py", "x = 1\n")
        violation = {"file": "invoice.py", "line": 1, "message": "Move it.", "note": "Move it."}
        verdict = {"structured_output": {"violations": [{**violation, "confidence": 0.4}]}}
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        claude = bin_dir / "claude"
        claude.write_text(f"#!/bin/sh\ncat > /dev/null\necho '{json.dumps(verdict)}'\n")
        claude.chmod(0o755)

        result = subprocess.run(
            [CODEGUARD, "eval"],
            cwd=package.root,
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(tmp_path), "PATH": f"{bin_dir}:{os.environ['PATH']}"},
        )

        assert result.stderr == (
            "python/rule-evals/responsibility-placement/invoice.py: "
            "responsibility-placement expected a violation with confidence 0.90, got:\n"
            "  line 1 (0.40): Move it.\n"
        )
        assert result.returncode == 1


class TestTestCommand:
    def test_ast_grep_outside_the_package_range_exits_2(self, tmp_path):
        package = GitRepo.init(tmp_path.resolve())
        write_package(package)
        package.write(
            "codeguard-package.yaml", "name: example\nrulesets: [python]\nast-grep: '<0.45'\n"
        )

        result = subprocess.run(
            [CODEGUARD, "test"], cwd=package.root, capture_output=True, text=True
        )

        _, traceback = result.stderr.split(TRACEBACK_HEADING)
        assert traceback.splitlines()[-2:] == [
            "codeguard.config.config_error.ConfigError: "
            f"{package.root}/codeguard-package.yaml is invalid:",
            f"  example supports ast-grep <0.45, not {BUNDLED_AST_GREP}",
        ]
        assert result.returncode == 2

    def test_unexpected_ruleset_entry_exits_2(self, tmp_path):
        package = GitRepo.init(tmp_path.resolve())
        write_package(package)
        package.write("python/rule-tests/judge/no-print-test.yml", "id: no-print\n")

        result = subprocess.run(
            [CODEGUARD, "test"], cwd=package.root, capture_output=True, text=True
        )

        _, traceback = result.stderr.split(TRACEBACK_HEADING)
        assert traceback.splitlines()[-2:] == [
            f"codeguard.config.config_error.ConfigError: {package.root}/python is invalid:",
            "  unexpected rule-tests/judge",
        ]
        assert result.returncode == 2

    def test_package_repo_runs_each_ruleset_tests(self, tmp_path):
        package = GitRepo.init(tmp_path.resolve())
        write_package(package)
        package.write(
            "python/rule-tests/pattern/no-print-test.yml",
            "id: no-print\nvalid:\n  - logging.info(1)\n",
        )

        result = subprocess.run(
            [CODEGUARD, "test"], cwd=package.root, capture_output=True, text=True
        )

        assert result.stdout == PASSING_NO_PRINT_TEST_REPORT
        assert result.returncode == 0

    def test_passing_rule_tests_exit_0(self, repo):
        repo.write(NO_PRINT_TEST, "id: no-print\nvalid:\n  - logging.info(1)\n")

        result = subprocess.run([CODEGUARD, "test"], cwd=repo.root, capture_output=True, text=True)

        assert result.stdout == PASSING_NO_PRINT_TEST_REPORT
        assert result.stderr == ""
        assert result.returncode == 0

    def test_stale_snapshot_entry_fails(self, repo):
        repo.write(
            NO_PRINT_TEST,
            "id: no-print\ninvalid:\n  - print(1)\n  - print(2)\n",
        )
        subprocess.run([CODEGUARD, "test", "--update-all"], cwd=repo.root, check=True)
        repo.write(NO_PRINT_TEST, "id: no-print\ninvalid:\n  - print(2)\n")

        result = subprocess.run([CODEGUARD, "test"], cwd=repo.root, capture_output=True, text=True)

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

    def test_invalid_binding_does_not_stop_rule_tests(self, repo):
        repo.write(NO_PRINT_TEST, "id: no-print\nvalid:\n  - logging.info(1)\n")
        repo.write(".codeguard/bindings/broken.yaml", "path: [a.py]\n")

        result = subprocess.run([CODEGUARD, "test"], cwd=repo.root, capture_output=True, text=True)

        assert result.stdout == PASSING_NO_PRINT_TEST_REPORT
        assert result.stderr == ""
        assert result.returncode == 0

    def test_failing_rule_tests_exit_1(self, repo):
        repo.write(NO_PRINT_TEST, "id: no-print\nvalid:\n  - print(1)\n")

        result = subprocess.run([CODEGUARD, "test"], cwd=repo.root, capture_output=True, text=True)

        assert result.stdout == (
            "Running 1 tests\n"
            "\n"
            "----------- Case Details -----------\n"
            "[Noisy] Expect no-print to report no issue, but some issues found in:\n"
            "\n"
            "  print(1)\n"
            "\n"
            "FAIL no-print  N\n"
            "\n"
        )
        assert result.stderr == (
            "Error: test failed. 0 passed; 1 failed;\n"
            "Help: You can use ast-grep playground to debug your rules and test cases.\n"
            "See also: https://ast-grep.github.io/playground.html\n"
            "\n"
        )
        assert result.returncode == 1
