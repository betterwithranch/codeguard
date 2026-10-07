import json
import subprocess
from typing import TextIO

from codeguard.checkout import Checkout
from codeguard.review import Review
from codeguard.rules import Rules
from codeguard.stop_event import StopEvent

PLAN_MODE = "plan"
HOOK_BLOCKS = 2
SKIPPED = Review(findings=())


def respond(stdin: TextIO, stderr: TextIO) -> int:
    result = review_at_stop(StopEvent.from_hook_input(json.load(stdin)))
    if not result.blocks:
        return 0
    result.write(stderr)
    return HOOK_BLOCKS


def review_at_stop(event: StopEvent) -> Review:
    if event.permission_mode == PLAN_MODE:
        return SKIPPED
    try:
        checkout = Checkout.containing(event.cwd)
        if checkout.operation_in_progress():
            return SKIPPED
        return Rules(checkout).review(checkout.changes("HEAD"))
    except (subprocess.CalledProcessError, FileNotFoundError):
        if event.cwd.is_dir():
            raise
        return SKIPPED
