import itertools
import re
import subprocess
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from google.genai import types

_MAX_LINES = 2000
_MAX_RESULTS = 200


@dataclass(frozen=True)
class FileTools:
    root: Path
    loaded_files: list[str] = field(default_factory=list)

    @property
    def declarations(self) -> list[types.FunctionDeclaration]:
        return [
            types.FunctionDeclaration(
                name="read_file",
                description=(
                    "Read a file in the working directory. Each line starts with its number "
                    f"and a tab. Returns at most {_MAX_LINES} lines from offset."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative to the root."},
                        "offset": {"type": "integer", "description": "First line. Default: 1."},
                    },
                    "required": ["path"],
                },
            ),
            types.FunctionDeclaration(
                name="grep",
                description=(
                    "Search the files in the working directory for a Python regular expression. "
                    f"Returns at most {_MAX_RESULTS} matches as path:line:text."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "glob": {
                            "type": "string",
                            "description": "Only search files matching this glob, like **/*.py.",
                        },
                    },
                    "required": ["pattern"],
                },
            ),
            types.FunctionDeclaration(
                name="glob",
                description=(
                    "List the files in the working directory matching a glob, like **/*.py. "
                    f"Returns at most {_MAX_RESULTS} paths."
                ),
                parameters_json_schema={
                    "type": "object",
                    "properties": {"pattern": {"type": "string"}},
                    "required": ["pattern"],
                },
            ),
        ]

    def call(self, name: str, arguments: Mapping[str, object]) -> str:
        tools: dict[str, Callable[..., str]] = {
            "read_file": self.read_file,
            "grep": self.grep,
            "glob": self.glob,
        }
        tool = tools.get(name)
        if tool is None:
            return f"Error: there is no tool {name}."
        try:
            return tool(**arguments)
        except (OSError, TypeError, ValueError, re.error) as error:
            return f"Error: {error}"

    def read_file(self, path: str, offset: int = 1) -> str:
        file = self._inside(path)
        self.loaded_files.append(path)
        lines = file.read_text(errors="replace").splitlines()
        start = max(offset, 1)
        return "".join(
            f"{number:>6}\t{line}\n"
            for number, line in enumerate(lines[start - 1 : start - 1 + _MAX_LINES], start=start)
        )

    def grep(self, pattern: str, glob: str = "**/*") -> str:
        expression = re.compile(pattern)
        matches = (
            (relative, f"{relative}:{number}:{line}")
            for relative, file in self._files(glob)
            for number, line in enumerate(_text_lines(file), start=1)
            if expression.search(line)
        )
        return self._shown(matches) or "No matches."

    def glob(self, pattern: str) -> str:
        return (
            self._shown((relative, relative) for relative, _ in self._files(pattern)) or "No files."
        )

    def _shown(self, lines: Iterator[tuple[str, str]]) -> str:
        kept = list(itertools.islice(lines, _MAX_RESULTS + 1))
        shown = kept[:_MAX_RESULTS]
        self.loaded_files.extend(dict.fromkeys(file for file, _ in shown))
        text = "\n".join(line for _, line in shown)
        if len(kept) > _MAX_RESULTS:
            return f"{text}\n(stopped at {_MAX_RESULTS} results)"
        return text

    def _inside(self, path: str) -> Path:
        root = self.root.resolve()
        resolved = (root / path).resolve()
        if not resolved.is_relative_to(root):
            raise ValueError(f"{path} is outside the working directory")
        return resolved

    def _files(self, pattern: str) -> Iterator[tuple[str, Path]]:
        root = self.root.resolve()
        for file in _candidates(root):
            relative = file.relative_to(root)
            hidden = any(part.startswith(".") for part in relative.parts)
            if (
                relative.full_match(pattern)
                and file.is_file()
                and not hidden
                and file.resolve().is_relative_to(root)
            ):
                yield str(relative), file


def _candidates(root: Path) -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if listed.returncode != 0:
        return sorted(root.rglob("*"))
    return sorted(root / name for name in listed.stdout.decode().split("\0") if name)


def _text_lines(file: Path) -> list[str]:
    try:
        return file.read_text().splitlines()
    except (OSError, UnicodeDecodeError):
        return []
