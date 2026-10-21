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
from dataclasses import dataclass
from pathlib import Path

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
    return items([repository.review(codeguard, host) for repository in repositories(Path.cwd())])


def repositories(directory: Path) -> list["Repository"]:
    """The repository holding the directory, or else each repository directly in it."""
    inside = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=directory,
        capture_output=True,
        check=False,
    )
    if inside.returncode == 0:
        return [Repository(directory, prefix="")]
    return [
        Repository(child, prefix=f"{child.name}/")
        for child in sorted(directory.iterdir())
        if (child / ".git").exists()
    ]


@dataclass(frozen=True)
class Review:
    diagnostics: list["Diagnostic"]
    failure: str | None = None


@dataclass(frozen=True)
class Repository:
    root: Path
    prefix: str

    def review(self, codeguard: str, host: str) -> Review:
        review = subprocess.run(
            [codeguard, "review", "--format", "json", "--judge-errors-as-warnings", "--host", host],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if review.returncode in (0, 1):
            try:
                raw = json.loads(review.stdout)["diagnostics"]
                return Review([Diagnostic.from_json(diagnostic, self.prefix) for diagnostic in raw])
            except (ValueError, KeyError):
                pass
        output = (review.stdout + review.stderr).rstrip()
        return Review([], failure=f"{NOT_REVIEWED}\n{output}")


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
    def from_json(cls, raw: dict[str, object], prefix: str) -> "Diagnostic":
        file, line, note = f"{prefix}{raw['file']}", raw["line"], raw["note"]
        return cls(
            location=file if line is None else f"{file}:{line}",
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


def items(reviews: list[Review]) -> dict[str, str]:
    diagnostics = [diagnostic for review in reviews for diagnostic in review.diagnostics]
    blocking = [diagnostic.render() for diagnostic in diagnostics if diagnostic.blocks]
    other = [diagnostic.render() for diagnostic in diagnostics if not diagnostic.blocks]
    failures = [review.failure for review in reviews if review.failure is not None]
    result: dict[str, str] = {}
    if blocking:
        result["decision"] = "block"
        result["reason"] = "\n".join([*blocking, REQUIRED_FIXES])
    messages = [*(["codeguard warnings:", *other] if other else []), *failures]
    if messages:
        result["systemMessage"] = "\n".join(messages)
    return result


if __name__ == "__main__":
    main()
