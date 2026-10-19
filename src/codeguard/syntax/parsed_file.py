from collections.abc import Iterable
from dataclasses import dataclass

from codeguard.syntax.syntax_node import SyntaxNode
from codeguard.syntax.syntax_table import NodeKind


@dataclass(frozen=True)
class ParsedFile:
    content: bytes
    nodes: tuple[SyntaxNode, ...]

    @property
    def definitions(self) -> tuple[str, ...]:
        return tuple(node.text for node in self.of_kind(NodeKind.DEFINITION))

    def enclosing_starts(self, lines: Iterable[int]) -> frozenset[int]:
        scopes = self.of_kind(NodeKind.SCOPE)
        return frozenset(
            scope.start_line for line in lines for scope in scopes if scope.spans(line)
        )

    def of_kind(self, kind: NodeKind) -> list[SyntaxNode]:
        return sorted((node for node in self.nodes if node.kind is kind), key=lambda n: n.start)

    def text(self, node: SyntaxNode) -> bytes:
        return self.content[node.start : node.end]

    def replaced(self, replacements: Iterable[tuple[SyntaxNode, bytes]]) -> bytes:
        content = self.content
        for node, text in sorted(replacements, key=lambda pair: pair[0].start, reverse=True):
            content = content[: node.start] + text + content[node.end :]
        return content
