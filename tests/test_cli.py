import json
import os
import subprocess
import sysconfig
from importlib import metadata
from pathlib import Path

import pytest
from claude_output import fake_claude_script, tool_result, tool_use
from git_repo import GitRepo
from rules_package import write_package

from codeguard.file_lock import exclusive_lock
from codeguard.review import Severity

CODEGUARD = Path(sysconfig.get_path("scripts")) / "codeguard"
BUNDLED_AST_GREP = metadata.version("ast-grep-cli")
NO_PRINT_TEST = ".codeguard/rule-tests/no-print-test.yml"
NO_PRINT_SNAPSHOT = ".codeguard/rule-tests/__snapshots__/no-print-snapshot.yml"
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

    def test_review_waits_for_a_running_review(self, repo, make_diagnostic):
        repo.write("a.py", "print(1)\n")
        diagnostic = make_diagnostic()

        with exclusive_lock(repo.root / ".git" / "codeguard-review.lock"):
            process = subprocess.Popen(
                [CODEGUARD, "review"], cwd=repo.root, stdout=subprocess.PIPE, text=True
            )
            with pytest.raises(subprocess.TimeoutExpired):
                process.wait(timeout=1)
        stdout, _ = process.communicate(timeout=30)

        assert stdout.startswith(
            f"a.py:1: error no-print: Use logging, not print. [{diagnostic.id}]\n"
        )
        assert process.returncode == 1

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
        assert git_error.startswith("fatal: not a git repository")
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
            "packages:\n  - kind: path\n    path: rules\n    rulesets:\n      python: {}\n",
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
            "  - kind: path\n"
            "    path: rules\n"
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
            "  - kind: path\n"
            "    path: rules\n"
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
            "  - kind: path\n"
            "    path: rules\n"
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


@pytest.fixture
def released_package(tmp_path_factory) -> GitRepo:
    package = GitRepo.init(tmp_path_factory.mktemp("released").resolve())
    write_package(package)
    package.commit("Add rules")
    package.git("tag", "v1.0.0")
    return package


def versioned_config(package: GitRepo) -> str:
    return (
        f"packages:\n  - kind: versioned\n    git: {package.file_url}\n    version: '>=1,<2'\n"
        "    rulesets:\n      python:\n        exclude: [responsibility-placement]\n"
    )


class TestUpdateCommand:
    def test_prints_each_locked_ref(self, repo, released_package):
        repo.write(".codeguard/config.yaml", versioned_config(released_package))

        result = subprocess.run(
            [CODEGUARD, "update"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == f"{released_package.file_url}: unlocked -> v1.0.0\n"
        assert result.stderr == ""
        assert result.returncode == 0


class TestReviewOfDeletedCode:
    def test_violation_on_the_class_that_lost_a_method_is_reported(
        self, repo, tmp_path, make_skill
    ):
        repo.write(".claude/skills/placement/SKILL.md", make_skill().text)
        repo.write(
            ".codeguard/bindings/placement.yaml",
            'skill: .claude/skills/placement\npaths: ["**/*.py"]\ntriggers: [any]\n',
        )
        repo.write(
            "service.py",
            "class ExampleService:\n"
            "    def execute(self):\n"
            "        return 1\n"
            "\n"
            "    def describe(self):\n"
            "        return 'service'\n",
        )
        repo.commit("Add the service")
        repo.write(
            "service.py",
            "class ExampleService:\n    def describe(self):\n        return 'service'\n",
        )
        violation = {"file": "service.py", "confidence": 1.0}
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        claude = bin_dir / "claude"
        claude.write_text(
            fake_claude_script(
                [
                    {**violation, "line": 1, "message": "The class lost its entry point."},
                    {**violation, "line": 2, "message": "Untouched method."},
                ]
            )
        )
        claude.chmod(0o755)

        result = subprocess.run(
            [CODEGUARD, "review"],
            cwd=repo.root,
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(tmp_path), "PATH": f"{bin_dir}:{os.environ['PATH']}"},
        )

        assert result.stdout.splitlines()[0].startswith(
            "service.py:1: error placement: The class lost its entry point."
        )
        assert "Untouched method." not in result.stdout


class TestReviewDryRun:
    def test_lists_judge_calls_without_calling_claude(self, repo, tmp_path, make_skill):
        repo.write(".claude/skills/placement/SKILL.md", make_skill().text)
        repo.write(
            ".codeguard/bindings/placement.yaml",
            'skill: .claude/skills/placement\npaths: ["**/*.py"]\ntriggers: [any]\n',
        )
        repo.write(".claude/skills/class-shape/SKILL.md", make_skill().text)
        repo.write(
            ".codeguard/bindings/class-shape.yaml",
            'skill: .claude/skills/class-shape\npaths: ["**/*.py"]\ntriggers: [class-header]\n',
        )
        repo.write("a.py", "x = 1\n")
        repo.write("b.rb", "x = 1\n")
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        claude = bin_dir / "claude"
        claude.write_text("#!/bin/sh\nexit 1\n")
        claude.chmod(0o755)

        result = subprocess.run(
            [CODEGUARD, "review", "--dry-run"],
            cwd=repo.root,
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(tmp_path), "PATH": f"{bin_dir}:{os.environ['PATH']}"},
        )

        assert result.stdout == (
            "Judge calls: 1 (0 cached, 1 to Claude), 1 skipped by triggers\n"
            "\n"
            "By rule:\n"
            "  claude  cached  skipped  rule\n"
            "       1       0        0  placement\n"
            "       0       0        1  class-shape\n"
            "\n"
            "By file:\n"
            "  claude  cached  skipped  file\n"
            "       1       0        1  a.py\n"
            "\n"
            "Calls by file:\n"
            "a.py\n"
            "  claude   placement\n"
            "  skipped  class-shape\n"
        )
        assert result.returncode == 0

    def test_pattern_rule_error_is_printed_and_exits_1(self, repo, make_diagnostic):
        repo.write("a.py", "print(1)\n")

        result = subprocess.run(
            [CODEGUARD, "review", "--dry-run"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == (
            f"{make_diagnostic()}\nJudge calls: 0 (0 cached, 0 to Claude), 0 skipped by triggers\n"
        )
        assert result.stderr == ""
        assert result.returncode == 1


class TestReviewJsonFormat:
    def test_prints_one_object_with_the_diagnostics(self, repo, make_diagnostic):
        repo.write("a.py", "print(1)\n")

        result = subprocess.run(
            [CODEGUARD, "review", "--format", "json"],
            cwd=repo.root,
            capture_output=True,
            text=True,
        )

        assert json.loads(result.stdout) == {"diagnostics": [make_diagnostic().as_json()]}
        assert result.returncode == 1

    def test_low_confidence_finding_is_a_warning_with_its_confidence(
        self, repo, tmp_path, make_skill, make_diagnostic
    ):
        bin_dir = judged_repo(repo, tmp_path, make_skill)
        violation = {"file": "a.py", "line": 1, "message": "Move it."}
        (bin_dir / "claude").write_text(fake_claude_script([{**violation, "confidence": 0.4}]))

        result = run_review(repo, tmp_path, bin_dir, "--format", "json")

        finding = make_diagnostic(
            judged=True,
            rule="placement",
            message="Move it.",
            note="Move it.",
            severity=Severity.WARNING,
            confidence=0.4,
        )
        assert json.loads(result.stdout) == {"diagnostics": [finding.as_json()]}
        assert result.returncode == 0

    def test_failed_judge_call_is_a_judge_error(self, repo, tmp_path, make_skill, make_diagnostic):
        bin_dir = judged_repo(repo, tmp_path, make_skill)

        result = run_review(repo, tmp_path, bin_dir, "--format", "json")

        judge_error = make_diagnostic(
            judge_error=True,
            rule="placement",
            note="claude exited with 1.\nstdout:\nrate limited\n\nstderr:\n",
        )
        assert json.loads(result.stdout) == {"diagnostics": [judge_error.as_json()]}

    def test_dry_run_has_no_json_format(self, repo):
        result = subprocess.run(
            [CODEGUARD, "review", "--dry-run", "--format", "json"],
            cwd=repo.root,
            capture_output=True,
            text=True,
        )

        assert "not allowed with argument" in result.stderr
        assert result.returncode == 2


class TestReviewJudgeCache:
    def test_cached_verdict_is_reused_until_a_file_the_judge_read_changes(
        self, repo, tmp_path, make_skill
    ):
        bin_dir = judged_repo(repo, tmp_path, make_skill)
        repo.write("orders/pricing.toml", "discount = 5\n")
        calls = tmp_path / "calls"
        (bin_dir / "claude").write_text(
            fake_claude_script(
                [],
                before=f"echo called >> {calls}\n",
                messages=(tool_use("Read", file_path="orders/pricing.toml"),),
            )
        )
        run_review(repo, tmp_path, bin_dir)
        run_review(repo, tmp_path, bin_dir)
        repo.write("orders/pricing.toml", "discount = 10\n")

        run_review(repo, tmp_path, bin_dir)

        assert calls.read_text() == "called\ncalled\n"

    @pytest.mark.parametrize("search", ["Grep", "Glob"])
    def test_cached_verdict_is_reused_until_a_file_a_search_found_changes(
        self, repo, tmp_path, make_skill, search
    ):
        bin_dir = judged_repo(repo, tmp_path, make_skill)
        repo.write("orders/pricing.toml", "discount = 5\n")
        calls = tmp_path / "calls"
        (bin_dir / "claude").write_text(
            fake_claude_script(
                [],
                before=f"echo called >> {calls}\n",
                messages=(
                    tool_use(search, "toolu_search", pattern="discount"),
                    tool_result("toolu_search", filenames=["orders/pricing.toml"]),
                ),
            )
        )
        run_review(repo, tmp_path, bin_dir)
        run_review(repo, tmp_path, bin_dir)
        repo.write("orders/pricing.toml", "discount = 10\n")

        run_review(repo, tmp_path, bin_dir)

        assert calls.read_text() == "called\ncalled\n"


class TestReviewJudgeErrorsAsWarnings:
    def test_judge_error_fails_the_review_without_the_flag(self, repo, tmp_path, make_skill):
        bin_dir = judged_repo(repo, tmp_path, make_skill)

        result = run_review(repo, tmp_path, bin_dir)

        assert result.stdout.startswith("a.py: error placement: The judge call failed")
        assert result.returncode == 1

    def test_judge_error_is_a_warning_with_the_flag(self, repo, tmp_path, make_skill):
        bin_dir = judged_repo(repo, tmp_path, make_skill)

        result = run_review(repo, tmp_path, bin_dir, "--judge-errors-as-warnings")

        assert result.stdout.startswith("a.py: warning placement: The judge call failed")
        assert result.returncode == 0

    def test_rule_violation_still_fails_the_review_with_the_flag(
        self, repo, tmp_path, make_skill, make_diagnostic
    ):
        bin_dir = judged_repo(repo, tmp_path, make_skill)
        repo.write("b.py", "print(1)\n")

        result = run_review(
            repo, tmp_path, bin_dir, "--judge-errors-as-warnings", "--format", "json"
        )

        violation = make_diagnostic(file="b.py")
        judge_error = make_diagnostic(
            judge_error=True,
            rule="placement",
            severity=Severity.WARNING,
            note="claude exited with 1.\nstdout:\nrate limited\n\nstderr:\n",
        )
        assert json.loads(result.stdout) == {
            "diagnostics": [violation.as_json(), judge_error.as_json()]
        }
        assert result.returncode == 1


class TestReviewHost:
    def test_host_changes_nothing_in_the_output(self, repo):
        repo.write("a.py", "print(1)\n")

        with_host, without_host = (
            subprocess.run(
                [CODEGUARD, "review", *arguments], cwd=repo.root, capture_output=True, text=True
            )
            for arguments in (["--host", "codex"], [])
        )

        assert with_host.stdout == without_host.stdout
        assert with_host.returncode == without_host.returncode


def judged_repo(repo: GitRepo, tmp_path: Path, make_skill) -> Path:
    """Bind a skill to every Python file, change a.py, and put a failing claude on PATH."""
    repo.write(".claude/skills/placement/SKILL.md", make_skill().text)
    repo.write(
        ".codeguard/bindings/placement.yaml",
        'skill: .claude/skills/placement\npaths: ["**/*.py"]\ntriggers: [any]\n',
    )
    repo.commit("Bind the skill")
    repo.write("a.py", "x = 1\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    claude = bin_dir / "claude"
    claude.write_text("#!/bin/sh\ncat > /dev/null\necho 'rate limited'\nexit 1\n")
    claude.chmod(0o755)
    return bin_dir


def run_review(
    repo: GitRepo, home: Path, bin_dir: Path, *arguments: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [CODEGUARD, "review", *arguments],
        cwd=repo.root,
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}"},
    )


class TestConfigCommand:
    def test_prints_the_default_without_a_config(self, repo):
        result = subprocess.run(
            [CODEGUARD, "config", "review_time_limit_minutes"],
            cwd=repo.root,
            capture_output=True,
            text=True,
        )

        assert result.stdout == "5\n"
        assert result.returncode == 0

    def test_prints_the_configured_setting(self, repo):
        repo.write(".codeguard/config.yaml", "review_time_limit_minutes: 10\n")

        result = subprocess.run(
            [CODEGUARD, "config", "review_time_limit_minutes"],
            cwd=repo.root,
            capture_output=True,
            text=True,
        )

        assert result.stdout == "10\n"
        assert result.returncode == 0


class TestReviewWithVersionedPackages:
    def test_unlocked_range_reviews_with_the_newest_tag(
        self, repo, released_package, make_diagnostic
    ):
        repo.write(".codeguard/config.yaml", versioned_config(released_package))
        repo.write("a.py", "x = 1\n")
        repo.commit("Opt in")
        released_package.git("rm", "--quiet", "python/rules/pattern/no-print.yml")
        released_package.commit("Remove no-print")
        released_package.git("tag", "v1.1.0")
        repo.write("a.py", "x = 1\nprint(x)\n")
        local = make_diagnostic(line=2)

        result = subprocess.run(
            [CODEGUARD, "review"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == f"{local}\n"
        assert result.returncode == 1

    def test_locked_range_reviews_with_the_locked_rules(
        self, repo, released_package, make_diagnostic
    ):
        repo.write(".codeguard/config.yaml", versioned_config(released_package))
        subprocess.run([CODEGUARD, "update"], cwd=repo.root, check=True)
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

    def test_newer_tag_in_range_reviews_with_the_locked_tag(
        self, repo, released_package, make_diagnostic
    ):
        repo.write(".codeguard/config.yaml", versioned_config(released_package))
        subprocess.run([CODEGUARD, "update"], cwd=repo.root, check=True)
        repo.write("a.py", "x = 1\n")
        repo.commit("Opt in")
        released_package.git("rm", "--quiet", "python/rules/pattern/no-print.yml")
        released_package.commit("Remove no-print")
        released_package.git("tag", "v1.1.0")
        repo.write("a.py", "x = 1\nprint(x)\n")
        local = make_diagnostic(line=2)
        packaged = make_diagnostic(line=2, rule="example/python/no-print", note=None)

        result = subprocess.run(
            [CODEGUARD, "review"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == f"{local}\n{packaged}\n"
        assert result.returncode == 1

    def test_latest_reviews_without_a_lock(self, repo, released_package, make_diagnostic):
        repo.write(".codeguard/config.yaml", versioned_config(released_package))
        repo.write("a.py", "x = 1\n")
        repo.commit("Opt in")
        repo.write("a.py", "x = 1\nprint(x)\n")
        local = make_diagnostic(line=2)
        packaged = make_diagnostic(line=2, rule="example/python/no-print", note=None)

        result = subprocess.run(
            [CODEGUARD, "review", "--latest"], cwd=repo.root, capture_output=True, text=True
        )

        assert result.stdout == f"{local}\n{packaged}\n"
        assert result.returncode == 1


class TestEvalCommand:
    def test_invalid_case_below_the_confidence_threshold_is_reported_and_exits_1(
        self, tmp_path, tmp_path_factory
    ):
        package = GitRepo.init(tmp_path_factory.mktemp("package").resolve())
        write_package(package)
        package.write(
            "python/rule-evals/responsibility-placement-eval.yml",
            "id: responsibility-placement\ninvalid:\n  - file: invoice.py\n    after: |\n"
            "      x = 1\n",
        )
        violation = {"file": "invoice.py", "line": 1, "message": "Move it."}
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        claude = bin_dir / "claude"
        claude.write_text(fake_claude_script([{**violation, "confidence": 0.4}]))
        claude.chmod(0o755)

        result = subprocess.run(
            [CODEGUARD, "eval"],
            cwd=package.root,
            capture_output=True,
            text=True,
            env={**os.environ, "HOME": str(tmp_path), "PATH": f"{bin_dir}:{os.environ['PATH']}"},
        )

        assert result.stderr == (
            "python/rule-evals/responsibility-placement-eval.yml invalid case 1: "
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
        package.write("python/rule-tests/triggers/no-print-test.yml", "id: no-print\n")

        result = subprocess.run(
            [CODEGUARD, "test"], cwd=package.root, capture_output=True, text=True
        )

        _, traceback = result.stderr.split(TRACEBACK_HEADING)
        assert traceback.splitlines()[-2:] == [
            f"codeguard.config.config_error.ConfigError: {package.root}/python is invalid:",
            "  unexpected rule-tests/triggers",
        ]
        assert result.returncode == 2

    def test_package_repo_runs_each_ruleset_tests(self, tmp_path):
        package = GitRepo.init(tmp_path.resolve())
        write_package(package)
        package.write(
            "python/rule-tests/no-print-test.yml",
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
            ".codeguard/rule-tests/__snapshots__/no-print-snapshot.yml: stale snapshot "
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
        assert result.stderr == (
            f"warning: triggers not checked: {repo.root}/.codeguard is invalid:\n"
            "  bindings.broken.yaml.skill: Field required\n"
            "  bindings.broken.yaml.paths: Field required\n"
            "  bindings.broken.yaml.path: Extra inputs are not permitted\n"
        )
        assert result.returncode == 0

    def test_broad_triggers_are_a_warning(self, repo, make_skill):
        repo.write(NO_PRINT_TEST, "id: no-print\nvalid:\n  - logging.info(1)\n")
        repo.write(".claude/skills/placement/SKILL.md", make_skill().text)
        repo.write(
            ".codeguard/bindings/placement.yaml",
            'skill: .claude/skills/placement\npaths: ["**/*.py"]\ntriggers: [any, fixture]\n',
        )

        result = subprocess.run([CODEGUARD, "test"], cwd=repo.root, capture_output=True, text=True)

        assert result.stderr == (
            "warning: placement: broad triggers any; "
            "a gate on the code its violations need skips more files\n"
        )
        assert result.returncode == 0

    def test_gate_tests_run_with_the_pattern_tests(self, repo):
        repo.write(
            ".codeguard/gates/enum-value.yml",
            "id: enum-value\nlanguage: python\nrule:\n  pattern: $X.value\n",
        )
        repo.write(
            ".codeguard/rule-tests/enum-value-test.yml",
            "id: enum-value\nvalid:\n  - status.name\ninvalid:\n  - status.value\n",
        )

        result = subprocess.run(
            [CODEGUARD, "test", "--update-all"], cwd=repo.root, capture_output=True, text=True
        )

        assert (repo.root / ".codeguard/rule-tests/__snapshots__/enum-value-snapshot.yml").is_file()
        assert result.returncode == 0

    def test_eval_case_whose_change_misses_the_triggers_exits_1(self, repo, make_skill):
        repo.write(NO_PRINT_TEST, "id: no-print\nvalid:\n  - logging.info(1)\n")
        repo.write(".claude/skills/placement/SKILL.md", make_skill().text)
        repo.write(
            ".codeguard/bindings/placement.yaml",
            'skill: .claude/skills/placement\npaths: ["**/*.py"]\ntriggers: [comment]\n',
        )
        repo.write(
            ".codeguard/rule-evals/placement-eval.yml",
            "id: placement\ninvalid:\n  - after: |\n      count = 1\n",
        )

        result = subprocess.run([CODEGUARD, "test"], cwd=repo.root, capture_output=True, text=True)

        assert result.stderr == (
            ".codeguard/rule-evals/placement-eval.yml invalid case 1: placement "
            "triggers comment miss the change, which touches code, module-statement, "
            "number-literal\n"
        )
        assert result.stdout == PASSING_NO_PRINT_TEST_REPORT
        assert result.returncode == 1

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
