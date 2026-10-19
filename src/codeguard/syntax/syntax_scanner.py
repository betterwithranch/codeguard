import subprocess
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from codeguard.ast_grep import AstGrep
from codeguard.syntax.parsed_file import ParsedFile
from codeguard.syntax.syntax_node import SyntaxNode
from codeguard.syntax.syntax_table import NodeKind, SyntaxTable


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
    def node(self) -> SyntaxNode:
        offset = self.range.byte_offset
        return SyntaxNode(kind=self.rule_id, start=offset.start, end=offset.end, text=self.text)


@dataclass(frozen=True)
class SyntaxScanner:
    ast_grep: AstGrep

    def scan(self, directory: Path) -> dict[str, ParsedFile]:
        paths = sorted(
            path.relative_to(directory).as_posix()
            for path in directory.rglob("*")
            if path.is_file()
        )
        files: dict[str, ParsedFile] = {}
        for table in SyntaxTable.supported():
            in_language = [path for path in paths if SyntaxTable.for_file(path) == table]
            if in_language:
                files.update(self._scan(directory, table, in_language))
        return files

    def _scan(self, directory: Path, table: SyntaxTable, files: list[str]) -> dict[str, ParsedFile]:
        command = [*self.ast_grep.executable, "scan", "--inline-rules", table.inline_rules]
        result = subprocess.run(
            [*command, "--json=stream", *files],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True,
        )
        matches = [_Match.model_validate_json(line) for line in result.stdout.splitlines()]
        return {
            file: ParsedFile(
                content=(directory / file).read_bytes(),
                nodes=tuple(match.node for match in matches if match.file == file),
            )
            for file in files
        }
