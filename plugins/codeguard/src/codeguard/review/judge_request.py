from dataclasses import dataclass
from pathlib import Path
from typing import Self

from codeguard.review.concern import Concern

TEMPLATE = (Path(__file__).parent / "judge.md").read_text()


@dataclass(frozen=True)
class JudgeRequest:
    instructions: str
    prompt: str

    @classmethod
    def from_concern(cls, concern: Concern, root: Path) -> Self:
        files = "\n\n".join(_numbered(root, file) for file in concern.files)
        return cls(instructions=TEMPLATE, prompt=f"{concern.skill.text.rstrip()}\n\n{files}\n")


def _numbered(root: Path, file: str) -> str:
    lines = (root / file).read_text().splitlines()
    body = "".join(f"{number}\t{line}\n" for number, line in enumerate(lines, start=1))
    return f'<file path="{file}">\n{body}</file>'
