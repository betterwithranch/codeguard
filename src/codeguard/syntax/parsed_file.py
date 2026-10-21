from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Self

from codeguard.config import ChangeKind
from codeguard.syntax.syntax_node import SyntaxNode
from codeguard.syntax.syntax_table import NodeKind

_PROSE = frozenset({ChangeKind.COMMENT, ChangeKind.DOCSTRING})


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

    def judged_lines(self, points: frozenset[int]) -> frozenset[int]:
        scopes = self.of_kind(NodeKind.SCOPE)
        return frozenset(line for point in points for line in _innermost_scope_lines(scopes, point))

    def touched_kinds(self, points: frozenset[int], base: Self | None) -> frozenset[str]:
        kinds = {kind for point in points for kind in self._kinds_spanning(point)}
        if points:
            kinds.add(ChangeKind.ANY)
        if self._scope_names != (base._scope_names if base else Counter()):
            kinds.add(ChangeKind.DEFINITION_ADDED_OR_REMOVED)
        return frozenset(kinds)

    def kinds_on(self, line: int) -> frozenset[str]:
        kinds = self._kinds_spanning(line)
        if any(node.spans(line) for node in self.of_kind(NodeKind.SCOPE_NAME)):
            kinds.add(ChangeKind.DEFINITION_ADDED_OR_REMOVED)
        return frozenset(kinds)

    def of_kind(self, kind: NodeKind | str) -> list[SyntaxNode]:
        return sorted((node for node in self.nodes if node.kind == kind), key=lambda n: n.start)

    def text(self, node: SyntaxNode) -> bytes:
        return self.content[node.start : node.end]

    def replaced(self, replacements: Iterable[tuple[SyntaxNode, bytes]]) -> bytes:
        content = self.content
        for node, text in sorted(replacements, key=lambda pair: pair[0].start, reverse=True):
            content = content[: node.start] + text + content[node.end :]
        return content

    def _kinds_spanning(self, line: int) -> set[str]:
        found: set[str] = {
            node.kind
            for node in self.nodes
            if not isinstance(node.kind, NodeKind) and node.spans(line)
        }
        if not found or not found <= _PROSE:
            found.add(ChangeKind.CODE)
        return found

    @property
    def _scope_names(self) -> Counter[str]:
        return Counter(node.text for node in self.of_kind(NodeKind.SCOPE_NAME))


def _innermost_scope_lines(scopes: list[SyntaxNode], point: int) -> range:
    enclosing = [scope for scope in scopes if scope.spans(point)]
    if not enclosing:
        return range(point, point + 1)
    innermost = min(enclosing, key=lambda scope: scope.end_line - scope.start_line)
    return range(innermost.start_line, innermost.end_line + 1)
