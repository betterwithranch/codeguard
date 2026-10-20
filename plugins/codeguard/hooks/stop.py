# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Review the agent's changes when it stops, for Claude Code and Codex alike.

Usage: uv run --script stop.py <host>

Blocking diagnostics go to the agent in `reason`; everything else, codeguard's own
failures included, goes to the user in `systemMessage`. Always exits 0 with one JSON
object, which both hosts read the same way.
"""

import json
import shutil
import subprocess
import sys
import textwrap

INSTALL = (
    "curl -LsSf https://raw.githubusercontent.com/betterwithranch/codeguard/v0/install.sh | sh"
)
NOT_REVIEWED = "codeguard review failed, so these changes were not reviewed."
REQUIRED_FIXES = (
    "These errors are required fixes, not suggestions. Fix the code. If the fix needs a "
    "decision, ask the user. Don't change .codeguard/config.yaml to silence them."
)


def main() -> None:
    host = sys.argv[1]
    sys.stdin.read()
    sys.stdout.write(f"{json.dumps(response(host))}\n")


def response(host: str) -> dict[str, str]:
    codeguard = shutil.which("codeguard")
    if codeguard is None:
        return {
            "systemMessage": "codeguard is not on PATH, so these changes were not reviewed. "
            f"Install it:\n{INSTALL}"
        }
    review = subprocess.run(
        [codeguard, "review", "--format", "json", "--judge-errors-as-warnings", "--host", host],
        capture_output=True,
        text=True,
        check=False,
    )
    if review.returncode in (0, 1):
        try:
            return items(json.loads(review.stdout)["diagnostics"])
        except (ValueError, KeyError):
            pass
    output = (review.stdout + review.stderr).rstrip()
    return {"systemMessage": f"{NOT_REVIEWED}\n{output}"}


def items(diagnostics: list[dict[str, object]]) -> dict[str, str]:
    blocking = [render(diagnostic) for diagnostic in diagnostics if diagnostic["blocks"]]
    other = [render(diagnostic) for diagnostic in diagnostics if not diagnostic["blocks"]]
    result: dict[str, str] = {}
    if blocking:
        result["decision"] = "block"
        result["reason"] = "\n".join([*blocking, REQUIRED_FIXES])
    if other:
        result["systemMessage"] = "\n".join(["codeguard warnings:", *other])
    return result


def render(diagnostic: dict[str, object]) -> str:
    file, line, note = diagnostic["file"], diagnostic["line"], diagnostic["note"]
    location = file if line is None else f"{file}:{line}"
    confidence = (
        f" (confidence {diagnostic['confidence']:.2f})"
        if diagnostic["category"] == "judged"
        else ""
    )
    summary = (
        f"{location}: {diagnostic['severity']} {diagnostic['rule']}: "
        f"{diagnostic['message']}{confidence} [{diagnostic['id']}]"
    )
    if note is None:
        return summary
    return f"{summary}\n{textwrap.indent(str(note).rstrip(), '  ')}"


if __name__ == "__main__":
    main()
