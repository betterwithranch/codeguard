import re
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Self

_HUNK = re.compile(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@")
# ASCII whitespace, the same set git treats as blank.
_BLANK = " \t\r\f\v"


@dataclass(frozen=True)
class Removal:
    """Rows a change removed, shown before the new line `before`; a violation in them is
    reported on `line`."""

    before: int
    line: int
    rows: tuple[str, ...]


@dataclass(frozen=True)
class ChangedLines:
    lines: Mapping[str, frozenset[int]]
    deletions: Mapping[str, frozenset[int]] = field(default_factory=dict)
    kinds: Mapping[str, frozenset[str]] = field(default_factory=dict)
    judged: Mapping[str, frozenset[int]] = field(default_factory=dict)
    kind_lines: Mapping[str, Mapping[str, frozenset[int]]] = field(default_factory=dict)
    removals: Mapping[str, tuple[Removal, ...]] = field(default_factory=dict)
    base: str | None = None

    @property
    def files(self) -> tuple[str, ...]:
        return tuple(sorted({*self.lines, *self.deletions}))

    def points(self, file: str) -> frozenset[int]:
        return self.lines.get(file, frozenset()) | self.deletions.get(file, frozenset())

    def with_kinds(self, kinds: Mapping[str, frozenset[str]]) -> Self:
        return replace(self, kinds=kinds)

    def with_judged_lines(self, judged: Mapping[str, frozenset[int]]) -> Self:
        return replace(self, judged=judged)

    def with_kind_lines(self, kind_lines: Mapping[str, Mapping[str, frozenset[int]]]) -> Self:
        return replace(self, kind_lines=kind_lines)

    def judged_lines(
        self, file: str, triggers: frozenset[str] = frozenset()
    ) -> frozenset[int] | None:
        spans = self.kind_lines.get(file, {})
        triggered = (spans.get(kind, frozenset()) for kind in triggers)
        return self.judged.get(file, self.points(file)).union(*triggered)

    def added_lines(self, file: str) -> frozenset[int] | None:
        return self.lines.get(file, frozenset())

    def removals_in(self, file: str) -> tuple[Removal, ...]:
        return self.removals.get(file, ())

    def kinds_of(self, file: str) -> frozenset[str] | None:
        return self.kinds.get(file)

    def covers(self, file: str, line: int | None, end_line: int | None = None) -> bool:
        if file not in self.files:
            return False
        if line is None:
            return True
        if end_line is not None:
            return any(line <= point <= end_line for point in self.points(file))
        return line in self.points(file)


@dataclass(frozen=True)
class AllLines:
    files: tuple[str, ...]

    def covers(self, file: str, line: int | None, end_line: int | None = None) -> bool:
        return True

    def kinds_of(self, file: str) -> frozenset[str] | None:
        return None

    def judged_lines(
        self, file: str, triggers: frozenset[str] = frozenset()
    ) -> frozenset[int] | None:
        return None

    def added_lines(self, file: str) -> frozenset[int] | None:
        return None

    def removals_in(self, file: str) -> tuple[Removal, ...]:
        return ()


@dataclass(frozen=True)
class WorkingTree:
    root: Path

    @classmethod
    def containing(cls, path: Path) -> Self:
        return cls(Path(_run_git(path, "rev-parse", "--show-toplevel").strip()))

    def changed_lines(self, base: str) -> ChangedLines:
        merge_base = self._git("merge-base", base, "HEAD").strip()
        diff = self._git_text(
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
        hunks = _hunks(diff)
        added, deletions = _changed_points(hunks)
        lines = {**added, **{file: self._code_lines(file) for file in untracked}}
        return ChangedLines(
            lines={file: numbers for file, numbers in lines.items() if numbers},
            deletions={file: numbers for file, numbers in deletions.items() if numbers},
            removals=_removals(hunks),
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
        lines = _rows((self.root / file).read_bytes())
        return frozenset(number for number, text in enumerate(lines, 1) if _holds_code(text))

    def _git_paths(self, command: str, *args: str) -> set[str]:
        return set(self._git(command, "-z", *args).split("\0")) - {""}

    def _git(self, *args: str) -> str:
        return _run_git(self.root, *args)

    def _git_text(self, *args: str) -> str:
        # Decoded without newline translation, so only "\n" ends a row, as it does for git.
        return self._git_bytes(*args).decode(errors="surrogateescape")

    def _git_bytes(self, *args: str) -> bytes:
        return subprocess.run(
            ["git", *args], cwd=self.root, stdout=subprocess.PIPE, check=True
        ).stdout


def _changed_points(
    hunks: Sequence["_Hunk"],
) -> tuple[dict[str, frozenset[int]], dict[str, frozenset[int]]]:
    added: dict[str, set[int]] = {}
    deletions: dict[str, set[int]] = {}
    for hunk in hunks:
        added.setdefault(hunk.file, set()).update(hunk.points)
        deletions.setdefault(hunk.file, set())
        if not hunk.points and hunk.removed:
            deletions[hunk.file].add(hunk.deletion_point)
    return _frozen(added), _frozen(deletions)


def _removals(hunks: Sequence["_Hunk"]) -> dict[str, tuple[Removal, ...]]:
    removals: dict[str, list[Removal]] = {}
    for hunk in hunks:
        if hunk.removed:
            removals.setdefault(hunk.file, []).append(hunk.removal)
    return {file: tuple(found) for file, found in removals.items()}


@dataclass
class _Hunk:
    file: str
    start: int
    points: set[int] = field(default_factory=set)
    added_rows: int = 0
    removed: list[str] = field(default_factory=list)

    @property
    def deletion_point(self) -> int:
        return max(self.start - 1 if self.added_rows else self.start, 1)

    @property
    def removal(self) -> Removal:
        # git numbers a hunk that only removes rows by the line before them.
        before = self.start if self.added_rows else self.start + 1
        line = min(self.points) if self.points else self.deletion_point
        return Removal(before, line, tuple(self.removed))

    def add(self, text: str) -> None:
        # A blank line changes nothing in any language, so only lines holding code count.
        if _holds_code(text):
            self.points.add(self.start + self.added_rows)
        self.added_rows += 1

    def remove(self, text: str) -> None:
        if _holds_code(text):
            self.removed.append(text)


def _hunks(diff: str) -> list[_Hunk]:
    hunks: list[_Hunk] = []
    file = ""
    in_header = False
    for row in _rows(diff):
        if row.startswith("diff --git "):
            in_header = True
        elif in_header and row.startswith("+++ "):
            # git ends the name with a tab when it holds a space.
            file = row.removeprefix("+++ ").removesuffix("\t")
        elif match := _HUNK.match(row):
            in_header = False
            hunks.append(_Hunk(file, int(match[1])))
        elif not in_header and hunks and row.startswith("-"):
            hunks[-1].remove(row[1:])
        elif not in_header and hunks and row.startswith("+"):
            hunks[-1].add(row[1:])
    return hunks


def _rows(text: str | bytes) -> list[str]:
    decoded = text if isinstance(text, str) else text.decode(errors="surrogateescape")
    return decoded.split("\n")


def _holds_code(text: str) -> bool:
    return bool(text.strip(_BLANK))


def _frozen(points: dict[str, set[int]]) -> dict[str, frozenset[int]]:
    return {file: frozenset(numbers) for file, numbers in points.items()}


def _run_git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, stdout=subprocess.PIPE, text=True, check=True
    ).stdout
