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

    def judged_lines(
        self, points: frozenset[int], removed: frozenset[int] = frozenset()
    ) -> frozenset[int]:
        scopes = self._standing(NodeKind.SCOPE, removed)
        members = self._standing(NodeKind.MEMBER_LIST, removed)
        statements = self.of_kind(NodeKind.STATEMENT)
        return frozenset(
            line
            for point in points
            for line in _context_lines(scopes, members, statements, removed, point)
        )

    def kind_lines(
        self, points: frozenset[int], removed: frozenset[int] = frozenset()
    ) -> dict[str, frozenset[int]]:
        spans: dict[str, set[int]] = {}
        for node in self.nodes:
            if (
                not isinstance(node.kind, NodeKind)
                and any(node.spans(point) for point in points)
                and not _removed(node, removed)
            ):
                spans.setdefault(node.kind, set()).update(node.lines)
        return {kind: frozenset(lines) for kind, lines in spans.items()}

    def touched_kinds(
        self, points: frozenset[int], base: Self | None, removed: frozenset[int] = frozenset()
    ) -> frozenset[str]:
        kinds = {kind for point in points for kind in self._kinds_spanning(point)}
        if base:
            kinds.update(kind for line in removed for kind in base._kinds_spanning(line))
        if points or removed:
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

    def _standing(self, kind: NodeKind, removed: frozenset[int]) -> list[SyntaxNode]:
        return [node for node in self.of_kind(kind) if not _removed(node, removed)]

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


def _context_lines(
    scopes: list[SyntaxNode],
    members: list[SyntaxNode],
    statements: list[SyntaxNode],
    removed: frozenset[int],
    point: int,
) -> set[int]:
    enclosing = [scope for scope in scopes if scope.spans(point)]
    innermost = min(enclosing, key=_size) if enclosing else None
    around = [
        node
        for node in statements
        if node.spans(point) and (innermost is None or _within(node, innermost))
    ]
    statement = min(around, key=_size) if around else None
    # A statement the change removed whole shows only its rows, as one it added shows itself.
    lines = {point} if statement is None or _removed(statement, removed) else set(statement.lines)
    if innermost is None:
        return lines
    body = next((node for node in members if node.spans(point) and _holds(innermost, node)), None)
    if body is None:
        return set(innermost.lines)
    # A change among a scope's members shows the scope's header, not its other members.
    return {*range(innermost.start_line, max(body.start_line, innermost.start_line + 1)), *lines}


def _size(node: SyntaxNode) -> int:
    return node.end_line - node.start_line


def _within(node: SyntaxNode, scope: SyntaxNode) -> bool:
    return scope.start_line <= node.start_line and node.end_line <= scope.end_line


def _holds(scope: SyntaxNode, body: SyntaxNode) -> bool:
    """Whether a member list is the scope's own, not that of a scope around it."""
    return _within(body, scope) and not _within(scope, body)


def _removed(node: SyntaxNode, removed: frozenset[int]) -> bool:
    """Whether the change removed every line of a base node."""
    return bool(removed) and removed.issuperset(node.lines)
