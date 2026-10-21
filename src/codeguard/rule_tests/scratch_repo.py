import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Self


@dataclass(frozen=True)
class ScratchRepo:
    root: Path

    @classmethod
    def init(cls, root: Path) -> Self:
        repo = cls(root)
        repo._git("init")
        return repo

    def write(self, files: Mapping[str, str]) -> None:
        for path, text in files.items():
            file = self.root / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text)

    def commit(self) -> None:
        self._git("add", "--all")
        self._git("commit", "--allow-empty", "--message", "Before")

    def _git(self, *args: str) -> None:
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=codeguard",
                "-c",
                "user.email=codeguard@localhost",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            cwd=self.root,
            check=True,
            capture_output=True,
        )
