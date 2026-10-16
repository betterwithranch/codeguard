import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Self


@dataclass(frozen=True)
class WorkingTree:
    root: Path

    @classmethod
    def containing(cls, path: Path) -> Self:
        return cls(Path(_run_git(path, "rev-parse", "--show-toplevel").strip()))

    def changed_files(self, base: str) -> tuple[str, ...]:
        merge_base = self._git("merge-base", base, "HEAD").strip()
        changed = self._git_paths("diff", "--name-only", "--diff-filter=d", merge_base)
        untracked = self._git_paths("ls-files", "--others", "--exclude-standard")
        return tuple(sorted(changed | untracked))

    def all_files(self) -> tuple[str, ...]:
        listed = self._git_paths("ls-files", "--cached", "--others", "--exclude-standard")
        return tuple(sorted(path for path in listed if (self.root / path).is_file()))

    def _git_paths(self, command: str, *args: str) -> set[str]:
        return set(self._git(command, "-z", *args).split("\0")) - {""}

    def _git(self, *args: str) -> str:
        return _run_git(self.root, *args)


def _run_git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, stdout=subprocess.PIPE, text=True, check=True
    ).stdout
