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
import os
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass

# Without an installed codeguard, uv runs this release, so nobody has to install it first.
RELEASE = "git+https://github.com/betterwithranch/codeguard@v0"
SOURCE_ENV_VAR = "CODEGUARD_SOURCE"
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
    review = subprocess.run(
        [*codeguard(), "review", "--format", "json", "--judge-errors-as-warnings", "--host", host],
        capture_output=True,
        text=True,
        check=False,
    )
    if review.returncode in (0, 1):
        try:
            raw = json.loads(review.stdout)["diagnostics"]
            return items([Diagnostic.from_json(diagnostic) for diagnostic in raw])
        except (ValueError, KeyError):
            pass
    output = (review.stdout + review.stderr).rstrip()
    return {"systemMessage": f"{NOT_REVIEWED}\n{output}"}


def codeguard() -> list[str]:
    installed = shutil.which("codeguard")
    if installed is not None:
        return [installed]
    source = os.environ.get(SOURCE_ENV_VAR, RELEASE)
    # uv caches a local checkout's build by its pyproject.toml, so edits to the code would
    # not run; an editable install runs the checkout as it is now.
    editable = ["--with-editable", source] if os.path.isdir(source) else []
    return ["uv", "tool", "run", "--quiet", "--from", source, *editable, "codeguard"]


@dataclass(frozen=True)
class Diagnostic:
    location: str
    severity: str
    rule: str
    message: str
    confidence: float | None
    id: str
    note: str | None
    blocks: bool

    @classmethod
    def from_json(cls, raw: dict[str, object]) -> "Diagnostic":
        file, line, note = raw["file"], raw["line"], raw["note"]
        return cls(
            location=str(file) if line is None else f"{file}:{line}",
            severity=str(raw["severity"]),
            rule=str(raw["rule"]),
            message=str(raw["message"]),
            confidence=float(str(raw["confidence"])) if raw["category"] == "judged" else None,
            id=str(raw["id"]),
            note=None if note is None else str(note),
            blocks=bool(raw["blocks"]),
        )

    def render(self) -> str:
        confidence = "" if self.confidence is None else f" (confidence {self.confidence:.2f})"
        summary = (
            f"{self.location}: {self.severity} {self.rule}: {self.message}{confidence} [{self.id}]"
        )
        if self.note is None:
            return summary
        return f"{summary}\n{textwrap.indent(self.note.rstrip(), '  ')}"


def items(diagnostics: list[Diagnostic]) -> dict[str, str]:
    blocking = [diagnostic.render() for diagnostic in diagnostics if diagnostic.blocks]
    other = [diagnostic.render() for diagnostic in diagnostics if not diagnostic.blocks]
    result: dict[str, str] = {}
    if blocking:
        result["decision"] = "block"
        result["reason"] = "\n".join([*blocking, REQUIRED_FIXES])
    if other:
        result["systemMessage"] = "\n".join(["codeguard warnings:", *other])
    return result


if __name__ == "__main__":
    main()
