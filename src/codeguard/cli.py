import argparse
import subprocess
import sys
import traceback
from pathlib import Path

from codeguard.rules import Rules
from codeguard.working_tree import WorkingTree

_EXIT_PASSED = 0
_EXIT_FAILED = 1
_EXIT_ERROR = 2


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
    review_command.set_defaults(run=_review)

    test_command = commands.add_parser("test", help="Run the project's rule tests.")
    test_command.add_argument(
        "--update-all",
        "-U",
        action="store_true",
        help="Regenerate snapshots and remove entries for cases that no longer exist.",
    )
    test_command.set_defaults(run=_test)

    args = parser.parse_args()
    try:
        return args.run(args)
    except subprocess.CalledProcessError as error:
        if error.stderr:
            sys.stderr.write(error.stderr)
        traceback.print_exc()
        return _EXIT_ERROR
    except Exception:
        traceback.print_exc()
        return _EXIT_ERROR


def _review(args: argparse.Namespace) -> int:
    working_tree = WorkingTree.containing(Path.cwd())
    scope = working_tree.all_lines() if args.all else working_tree.changed_lines(args.base)
    result = Rules(working_tree).review(scope)
    result.write(sys.stdout)
    return _EXIT_FAILED if result.blocks else _EXIT_PASSED


def _test(args: argparse.Namespace) -> int:
    tests = Rules(WorkingTree.containing(Path.cwd())).tests
    result = tests.update_snapshots() if args.update_all else tests.run()
    result.write(sys.stderr)
    return _EXIT_PASSED if result.passed else _EXIT_FAILED
