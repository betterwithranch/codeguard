from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from codeguard.syntax.syntax import NodeKind


@dataclass(frozen=True)
class SourceNode:
    kind: NodeKind
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class SourceFile:
    content: bytes
    nodes: tuple[SourceNode, ...]

    @property
    def definitions(self) -> tuple[str, ...]:
        return tuple(node.text for node in self._of_kind(NodeKind.DEFINITION))

    def without_comments(self) -> bytes:
        return self._replace((node, b"") for node in self._of_kind(NodeKind.COMMENT))

    def with_imports_reversed(self) -> bytes:
        imports = self._of_kind(NodeKind.IMPORT)
        return self._replace(
            (node, self._text(moved))
            for node, moved in zip(imports, reversed(imports), strict=True)
        )

    def renamed(self, names: Mapping[str, str]) -> bytes:
        return self._replace(
            (node, names[node.text].encode())
            for node in self._of_kind(NodeKind.NAME)
            if node.text in names
        )

    def _of_kind(self, kind: NodeKind) -> list[SourceNode]:
        return sorted((node for node in self.nodes if node.kind is kind), key=lambda n: n.start)

    def _text(self, node: SourceNode) -> bytes:
        return self.content[node.start : node.end]

    def _replace(self, replacements: Iterable[tuple[SourceNode, bytes]]) -> bytes:
        content = self.content
        for node, text in sorted(replacements, key=lambda pair: pair[0].start, reverse=True):
            content = content[: node.start] + text + content[node.end :]
        return content
