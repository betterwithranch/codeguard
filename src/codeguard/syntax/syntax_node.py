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

    def spans(self, line: int) -> bool:
        return self.start_line <= line <= self.end_line
