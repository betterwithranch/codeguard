import argparse
import subprocess
import sys
import traceback
from pathlib import Path

from codeguard.packages import PackageUpdate
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
    review_command.add_argument(
        "--latest",
        action="store_true",
        help="Use the newest tag in each package's version range instead of the lock file.",
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

    eval_command = commands.add_parser(
        "eval", help="Check that each judge rule flags its invalid cases and passes its valid ones."
    )
    eval_command.set_defaults(run=_eval)

    update_command = commands.add_parser(
        "update", help="Lock each package's version range to its newest matching tag."
    )
    update_command.set_defaults(run=_update)

    args = parser.parse_args()
    try:
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


def _review(args: argparse.Namespace) -> int:
    working_tree = WorkingTree.containing(Path.cwd())
    scope = working_tree.all_lines() if args.all else working_tree.changed_lines(args.base)
    result = Rules(working_tree, latest=args.latest).review(scope)
    result.write(sys.stdout)
    return _EXIT_FAILED if result.blocks else _EXIT_PASSED


def _test(args: argparse.Namespace) -> int:
    tests = Rules(WorkingTree.containing(Path.cwd())).tests
    result = tests.update_snapshots() if args.update_all else tests.run()
    result.write(sys.stderr)
    return _EXIT_PASSED if result.passed else _EXIT_FAILED


def _eval(args: argparse.Namespace) -> int:
    result = Rules(WorkingTree.containing(Path.cwd())).evaluate()
    result.write(sys.stderr)
    return _EXIT_PASSED if result.passed else _EXIT_FAILED


def _update(args: argparse.Namespace) -> int:
    for update in PackageUpdate(WorkingTree.containing(Path.cwd()).root).run():
        sys.stdout.write(f"{update}\n")
    return _EXIT_PASSED
