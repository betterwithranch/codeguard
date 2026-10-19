import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Self

_HUNK = re.compile(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class ChangedLines:
    lines: Mapping[str, frozenset[int]]
    deletions: Mapping[str, frozenset[int]] = field(default_factory=dict)
    node_starts: Mapping[str, frozenset[int]] = field(default_factory=dict)

    @property
    def files(self) -> tuple[str, ...]:
        return tuple(sorted({*self.lines, *self.deletions}))

    def points(self, file: str) -> frozenset[int]:
        return self.lines.get(file, frozenset()) | self.deletions.get(file, frozenset())

    def with_node_starts(self, node_starts: Mapping[str, frozenset[int]]) -> Self:
        return replace(self, node_starts=node_starts)

    def covers(self, file: str, line: int | None, end_line: int | None = None) -> bool:
        if file not in self.files:
            return False
        if line is None:
            return True
        if end_line is not None:
            return any(line <= point <= end_line for point in self.points(file))
        return line in self.points(file) or line in self.node_starts.get(file, frozenset())


@dataclass(frozen=True)
class AllLines:
    files: tuple[str, ...]

    def covers(self, file: str, line: int | None, end_line: int | None = None) -> bool:
        return True


@dataclass(frozen=True)
class WorkingTree:
    root: Path

    @classmethod
    def containing(cls, path: Path) -> Self:
        return cls(Path(_run_git(path, "rev-parse", "--show-toplevel").strip()))

    def changed_lines(self, base: str) -> ChangedLines:
        merge_base = self._git("merge-base", base, "HEAD").strip()
        diff = self._git(
            "-c",
            "core.quotePath=false",
            "diff",
            "-U0",
            "--no-color",
            "--no-ext-diff",
            "--no-prefix",
            "--diff-filter=d",
            merge_base,
        )
        untracked = self._git_paths("ls-files", "--others", "--exclude-standard")
        added, deletions = _changed_points(diff)
        lines = {**added, **{file: self._every_line(file) for file in untracked}}
        return ChangedLines(
            lines={file: numbers for file, numbers in lines.items() if numbers},
            deletions={file: numbers for file, numbers in deletions.items() if numbers},
        )

    def all_lines(self) -> AllLines:
        listed = self._git_paths("ls-files", "--cached", "--others", "--exclude-standard")
        return AllLines(tuple(sorted(path for path in listed if (self.root / path).is_file())))

    def git_path(self, name: str) -> Path:
        return self.root / self._git("rev-parse", "--git-path", name).strip()

    def _every_line(self, file: str) -> frozenset[int]:
        count = len((self.root / file).read_bytes().splitlines())
        return frozenset(range(1, count + 1))

    def _git_paths(self, command: str, *args: str) -> set[str]:
        return set(self._git(command, "-z", *args).split("\0")) - {""}

    def _git(self, *args: str) -> str:
        return _run_git(self.root, *args)


def _changed_points(diff: str) -> tuple[dict[str, frozenset[int]], dict[str, frozenset[int]]]:
    added: dict[str, set[int]] = {}
    deletions: dict[str, set[int]] = {}
    file = ""
    in_header = False
    for row in diff.splitlines():
        if row.startswith("diff --git "):
            in_header = True
        elif in_header and row.startswith("+++ "):
            file = row.removeprefix("+++ ")
            added[file] = set()
            deletions[file] = set()
        elif match := _HUNK.match(row):
            in_header = False
            start, count = int(match[1]), int(match[2] or 1)
            if count:
                added[file].update(range(start, start + count))
            else:
                deletions[file].add(max(start, 1))
    return _frozen(added), _frozen(deletions)


def _frozen(points: dict[str, set[int]]) -> dict[str, frozenset[int]]:
    return {file: frozenset(numbers) for file, numbers in points.items()}


def _run_git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, stdout=subprocess.PIPE, text=True, check=True
    ).stdout
