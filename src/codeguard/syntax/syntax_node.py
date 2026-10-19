from dataclasses import dataclass

from codeguard.syntax.syntax_table import NodeKind


@dataclass(frozen=True)
class SyntaxNode:
    kind: NodeKind
    start: int
    end: int
    text: str
