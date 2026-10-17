import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from codeguard.ast_grep import AstGrep
from codeguard.config import Skip
from codeguard.syntax.source_file import SourceFile, SourceNode
from codeguard.syntax.syntax import NodeKind, Syntax

_RENAMED = "name_{}"


class _ByteOffset(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    start: int
    end: int


class _Range(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    byte_offset: _ByteOffset = Field(alias="byteOffset")


class _Match(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    rule_id: NodeKind = Field(alias="ruleId")
    file: str
    text: str
    range: _Range

    @property
    def node(self) -> SourceNode:
        offset = self.range.byte_offset
        return SourceNode(kind=self.rule_id, start=offset.start, end=offset.end, text=self.text)


@dataclass(frozen=True)
class SourceTree:
    files: Mapping[str, SourceFile]

    @classmethod
    def scan(cls, ast_grep: AstGrep, directory: Path) -> Self:
        paths = sorted(
            path.relative_to(directory).as_posix()
            for path in directory.rglob("*")
            if path.is_file()
        )
        files: dict[str, SourceFile] = {}
        for syntax in Syntax.supported():
            in_language = [path for path in paths if Syntax.for_file(path) == syntax]
            if in_language:
                files.update(_scan(ast_grep, directory, syntax, in_language))
        return cls(files)

    def variant(self, skip: Skip) -> dict[str, bytes]:
        names = self._renames()
        changed = {file: _transformed(source, skip, names) for file, source in self.files.items()}
        return {
            file: content
            for file, content in changed.items()
            if content != self.files[file].content
        }

    def _renames(self) -> dict[str, str]:
        defined = dict.fromkeys(
            name for source in self.files.values() for name in source.definitions
        )
        return {name: _RENAMED.format(number) for number, name in enumerate(defined, start=1)}


def _transformed(source: SourceFile, skip: Skip, names: Mapping[str, str]) -> bytes:
    match skip:
        case Skip.RENAMES:
            return source.renamed(names)
        case Skip.COMMENTS:
            return source.without_comments()
        case Skip.IMPORTS:
            return source.with_imports_reversed()


def _scan(
    ast_grep: AstGrep, directory: Path, syntax: Syntax, files: list[str]
) -> dict[str, SourceFile]:
    command = [*ast_grep.executable, "scan", "--inline-rules", syntax.inline_rules, "--json=stream"]
    result = subprocess.run(
        [*command, *files], cwd=directory, capture_output=True, text=True, check=True
    )
    matches = [_Match.model_validate_json(line) for line in result.stdout.splitlines()]
    return {
        file: SourceFile(
            content=(directory / file).read_bytes(),
            nodes=tuple(match.node for match in matches if match.file == file),
        )
        for file in files
    }
