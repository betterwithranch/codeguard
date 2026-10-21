import argparse
import os
import subprocess
import sys
import traceback
from pathlib import Path

import logfire

from codeguard.config import ConfigLoader
from codeguard.file_lock import exclusive_lock
from codeguard.packages import PackageUpdate
from codeguard.rules import Rules, check_installed_evals
from codeguard.working_tree import AllLines, ChangedLines, WorkingTree

_EXIT_PASSED = 0
_EXIT_FAILED = 1
_EXIT_ERROR = 2
_REVIEW_LOCK = "codeguard-review.lock"


def main() -> int:
    parser = argparse.ArgumentParser(prog="codeguard")
    commands = parser.add_subparsers(required=True)

    review_command = commands.add_parser(
        "review", help="Check the changed files against the project's rules."
    )
    scope = review_command.add_mutually_exclusive_group()
    scope.add_argument(
        "--base",
        default="HEAD",
        help="Include changes since the merge base with this ref. Default: uncommitted changes.",
    )
    scope.add_argument(
        "--all",
        action="store_true",
        help="Check every tracked and untracked file.",
    )
    review_command.add_argument(
        "--latest",
        action="store_true",
        help="Use the newest tag in each package's version range instead of the lock file.",
    )
    output = review_command.add_mutually_exclusive_group()
    output.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the pattern rules and list the judge calls the review would make, "
        "without calling the judge.",
    )
    output.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Print diagnostics as text lines or as one JSON object. Default: text.",
    )
    review_command.add_argument(
        "--judge-errors-as-warnings",
        action="store_true",
        help="Report each judge call that couldn't complete as a warning, so it doesn't fail "
        "the review.",
    )
    review_command.add_argument(
        "--host",
        help="Name the caller (such as claude-code or codex) in telemetry. Changes nothing else.",
    )
    review_command.set_defaults(run=_review)

    test_command = commands.add_parser("test", help="Run the project's rule tests.")
    test_command.add_argument(
        "package",
        nargs="?",
        type=Path,
        help="Test the rule package in this directory. Default: the current repository.",
    )
    test_command.add_argument(
        "--update-all",
        "-U",
        action="store_true",
        help="Regenerate snapshots and remove entries for cases that no longer exist.",
    )
    test_command.set_defaults(run=_test)

    eval_command = commands.add_parser(
        "eval", help="Check that each judge rule flags its invalid cases and passes its valid ones."
    )
    eval_command.add_argument(
        "package",
        nargs="?",
        type=Path,
        help="Evaluate the rule package in this directory. Default: the current repository.",
    )
    eval_command.add_argument(
        "--repeat",
        type=_positive_int,
        default=1,
        help="Judge each case this many times. More than once skips the cache. Default: 1.",
    )
    eval_command.set_defaults(run=_eval)

    update_command = commands.add_parser(
        "update", help="Lock each package's version range to its newest matching tag."
    )
    update_command.set_defaults(run=_update)

    config_command = commands.add_parser(
        "config", help="Print a setting from .codeguard/config.yaml, or its default."
    )
    config_command.add_argument("setting", choices=("review_time_limit_minutes",))
    config_command.set_defaults(run=_config)

    args = parser.parse_args()
    _configure_telemetry()
    try:
        with logfire.span("codeguard {command}", command=args.run.__name__.lstrip("_")):
            return args.run(args)
    except subprocess.CalledProcessError as error:
        if error.stdout:
            sys.stderr.write(error.stdout)
        if error.stderr:
            sys.stderr.write(error.stderr)
        traceback.print_exc()
        return _EXIT_ERROR
    except Exception:
        traceback.print_exc()
        return _EXIT_ERROR


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"{value} is not a positive number")
    return number


def _configure_telemetry() -> None:
    logfire.configure(
        send_to_logfire="if-token-present",
        service_name="codeguard",
        environment="ci" if os.environ.get("GITHUB_ACTIONS") == "true" else "local",
        console=False,
        inspect_arguments=False,
    )


def _review(args: argparse.Namespace) -> int:
    working_tree = WorkingTree.containing(Path.cwd())
    if args.dry_run:
        rules = Rules(working_tree, latest=args.latest)
        scope = _scope(working_tree, args)
        result = rules.check_patterns(scope)
        result.write(sys.stdout)
        rules.plan(scope).write(sys.stdout)
        return _EXIT_FAILED if result.blocks else _EXIT_PASSED
    with exclusive_lock(working_tree.git_path(_REVIEW_LOCK)):
        scope = _scope(working_tree, args)
        with logfire.span(
            "review {repository}",
            repository=working_tree.root.name,
            files=len(scope.files),
            latest=args.latest,
            host=args.host,
        ) as span:
            result = Rules(working_tree, latest=args.latest).review(scope)
            if args.judge_errors_as_warnings:
                result = result.with_judge_errors_as_warnings()
            span.set_attributes(
                {
                    "diagnostics": len(result.diagnostics),
                    "errors": sum(diagnostic.blocks for diagnostic in result.diagnostics),
                }
            )
    if args.format == "json":
        result.write_json(sys.stdout)
    else:
        result.write(sys.stdout)
    return _EXIT_FAILED if result.blocks else _EXIT_PASSED


def _scope(working_tree: WorkingTree, args: argparse.Namespace) -> ChangedLines | AllLines:
    return working_tree.all_lines() if args.all else working_tree.changed_lines(args.base)


def _test(args: argparse.Namespace) -> int:
    tests = Rules(_working_tree(args.package)).tests
    result = tests.update_snapshots() if args.update_all else tests.run()
    result.write(sys.stdout)
    return _EXIT_PASSED if result.passed else _EXIT_FAILED


def _eval(args: argparse.Namespace) -> int:
    check_installed_evals()
    # pydantic-evals takes about 0.4s to import, so only codeguard eval loads it.
    from codeguard.rules.rule_evaluation import RuleEvaluation  # noqa: PLC0415

    result = RuleEvaluation(Rules(_working_tree(args.package))).run(args.repeat)
    result.write(sys.stdout)
    return _EXIT_PASSED if result.passed else _EXIT_FAILED


def _working_tree(package: Path | None) -> WorkingTree:
    return WorkingTree(package.resolve()) if package else WorkingTree.containing(Path.cwd())


def _config(args: argparse.Namespace) -> int:
    config = ConfigLoader(WorkingTree.containing(Path.cwd()).root).load()
    sys.stdout.write(f"{getattr(config, args.setting)}\n")
    return _EXIT_PASSED


def _update(args: argparse.Namespace) -> int:
    for update in PackageUpdate(WorkingTree.containing(Path.cwd()).root).run():
        sys.stdout.write(f"{update}\n")
    return _EXIT_PASSED
