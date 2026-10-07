import argparse
import subprocess
import sys
from pathlib import Path

from codeguard import stop_hook
from codeguard.checkout import Checkout
from codeguard.rules import Rules


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

    hook_command = commands.add_parser("hook", help="Run as an agent hook.")
    hook_events = hook_command.add_subparsers(required=True)
    stop_command = hook_events.add_parser(
        "stop", help="Block the agent's Stop when its uncommitted changes break a rule."
    )
    stop_command.set_defaults(run=lambda _: stop_hook.respond(sys.stdin, sys.stderr))

    args = parser.parse_args()
    try:
        return args.run(args)
    except subprocess.CalledProcessError as error:
        if error.stderr:
            sys.stderr.write(error.stderr)
        raise


def _review(args: argparse.Namespace) -> int:
    checkout = Checkout.containing(Path.cwd())
    files = checkout.all_files() if args.all else checkout.changes(args.base)
    result = Rules(checkout).review(files)
    result.write(sys.stdout)
    return 1 if result.blocks else 0


def _test(args: argparse.Namespace) -> int:
    tests = Rules(Checkout.containing(Path.cwd())).tests
    result = tests.update_snapshots() if args.update_all else tests.run()
    result.write(sys.stderr)
    return 0 if result.passed else 1
