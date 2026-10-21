import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Self

_HUNK = re.compile(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class ChangedLines:
    lines: Mapping[str, frozenset[int]]
    deletions: Mapping[str, frozenset[int]] = field(default_factory=dict)
    node_starts: Mapping[str, frozenset[int]] = field(default_factory=dict)
    kinds: Mapping[str, frozenset[str]] = field(default_factory=dict)
    judged: Mapping[str, frozenset[int]] = field(default_factory=dict)
    base: str | None = None

    @property
    def files(self) -> tuple[str, ...]:
        return tuple(sorted({*self.lines, *self.deletions}))

    def points(self, file: str) -> frozenset[int]:
        return self.lines.get(file, frozenset()) | self.deletions.get(file, frozenset())

    def with_node_starts(self, node_starts: Mapping[str, frozenset[int]]) -> Self:
        return replace(self, node_starts=node_starts)

    def with_kinds(self, kinds: Mapping[str, frozenset[str]]) -> Self:
        return replace(self, kinds=kinds)

    def with_judged_lines(self, judged: Mapping[str, frozenset[int]]) -> Self:
        return replace(self, judged=judged)

    def judged_lines(self, file: str) -> frozenset[int] | None:
        return self.judged.get(file, self.points(file))

    def kinds_of(self, file: str) -> frozenset[str] | None:
        return self.kinds.get(file)

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

    def kinds_of(self, file: str) -> frozenset[str] | None:
        return None

    def judged_lines(self, file: str) -> frozenset[int] | None:
        return None


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
        lines = {**added, **{file: self._code_lines(file) for file in untracked}}
        return ChangedLines(
            lines={file: numbers for file, numbers in lines.items() if numbers},
            deletions={file: numbers for file, numbers in deletions.items() if numbers},
            base=merge_base,
        )

    def base_contents(self, base: str, files: Sequence[str]) -> dict[str, bytes]:
        if not files:
            return {}
        in_base = self._git_paths("ls-tree", "-r", "--name-only", base, "--", *files)
        return {
            file: self._git_bytes("show", f"{base}:{file}") for file in files if file in in_base
        }

    def all_lines(self) -> AllLines:
        listed = self._git_paths("ls-files", "--cached", "--others", "--exclude-standard")
        return AllLines(tuple(sorted(path for path in listed if (self.root / path).is_file())))

    def git_path(self, name: str) -> Path:
        return self.root / self._git("rev-parse", "--git-path", name).strip()

    def _code_lines(self, file: str) -> frozenset[int]:
        lines = (self.root / file).read_bytes().splitlines()
        return frozenset(number for number, text in enumerate(lines, 1) if _holds_code(text))

    def _git_paths(self, command: str, *args: str) -> set[str]:
        return set(self._git(command, "-z", *args).split("\0")) - {""}

    def _git(self, *args: str) -> str:
        return _run_git(self.root, *args)

    def _git_bytes(self, *args: str) -> bytes:
        return subprocess.run(
            ["git", *args], cwd=self.root, stdout=subprocess.PIPE, check=True
        ).stdout


def _changed_points(diff: str) -> tuple[dict[str, frozenset[int]], dict[str, frozenset[int]]]:
    added: dict[str, set[int]] = {}
    deletions: dict[str, set[int]] = {}
    for hunk in _hunks(diff):
        points = hunk.points
        added.setdefault(hunk.file, set()).update(points)
        deletions.setdefault(hunk.file, set())
        if not points and any(_holds_code(text) for text in hunk.removed):
            deletions[hunk.file].add(max(hunk.start - 1 if hunk.added else hunk.start, 1))
    return _frozen(added), _frozen(deletions)


@dataclass
class _Hunk:
    file: str
    start: int
    removed: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)

    @property
    def points(self) -> set[int]:
        # A blank line changes nothing in any language, so only lines holding code count.
        return {self.start + offset for offset, text in enumerate(self.added) if _holds_code(text)}


def _hunks(diff: str) -> list[_Hunk]:
    hunks: list[_Hunk] = []
    file = ""
    in_header = False
    for row in diff.splitlines():
        if row.startswith("diff --git "):
            in_header = True
        elif in_header and row.startswith("+++ "):
            file = row.removeprefix("+++ ")
        elif match := _HUNK.match(row):
            in_header = False
            hunks.append(_Hunk(file, int(match[1])))
        elif not in_header and hunks and row.startswith("-"):
            hunks[-1].removed.append(row[1:])
        elif not in_header and hunks and row.startswith("+"):
            hunks[-1].added.append(row[1:])
    return hunks


def _holds_code(text: str | bytes) -> bool:
    return bool(text.strip())


def _frozen(points: dict[str, set[int]]) -> dict[str, frozenset[int]]:
    return {file: frozenset(numbers) for file, numbers in points.items()}


def _run_git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, stdout=subprocess.PIPE, text=True, check=True
    ).stdout
