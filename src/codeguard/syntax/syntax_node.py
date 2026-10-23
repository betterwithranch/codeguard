from dataclasses import dataclass

from codeguard.syntax.syntax_table import NodeKind


@dataclass(frozen=True)
class SyntaxNode:
    kind: NodeKind | str
    start: int
    end: int
    text: str
    start_line: int
    end_line: int

    @property
    def lines(self) -> range:
        return range(self.start_line, self.end_line + 1)

    def spans(self, line: int) -> bool:
        return self.start_line <= line <= self.end_line
