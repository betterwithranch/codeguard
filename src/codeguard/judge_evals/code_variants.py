from collections.abc import Mapping
from dataclasses import dataclass

from codeguard.config import Skip
from codeguard.syntax import NodeKind, ParsedFile

_RENAMED = "name_{}"


@dataclass(frozen=True)
class CodeVariants:
    files: Mapping[str, ParsedFile]

    def variant(self, skip: Skip) -> dict[str, bytes]:
        names = self._renames()
        changed = {file: _transformed(parsed, skip, names) for file, parsed in self.files.items()}
        return {
            file: content
            for file, content in changed.items()
            if content != self.files[file].content
        }

    def _renames(self) -> dict[str, str]:
        defined = dict.fromkeys(
            name for parsed in self.files.values() for name in parsed.definitions
        )
        return {name: _RENAMED.format(number) for number, name in enumerate(defined, start=1)}


def _transformed(parsed: ParsedFile, skip: Skip, names: Mapping[str, str]) -> bytes:
    match skip:
        case Skip.RENAMES:
            return _renamed(parsed, names)
        case Skip.COMMENTS:
            return _without_comments(parsed)
        case Skip.IMPORTS:
            return _with_imports_reversed(parsed)


def _renamed(parsed: ParsedFile, names: Mapping[str, str]) -> bytes:
    return parsed.replaced(
        (node, names[node.text].encode())
        for node in parsed.of_kind(NodeKind.NAME)
        if node.text in names
    )


def _without_comments(parsed: ParsedFile) -> bytes:
    return parsed.replaced((node, b"") for node in parsed.of_kind(NodeKind.COMMENT))


def _with_imports_reversed(parsed: ParsedFile) -> bytes:
    imports = parsed.of_kind(NodeKind.IMPORT)
    return parsed.replaced(
        (node, parsed.text(moved)) for node, moved in zip(imports, reversed(imports), strict=True)
    )
