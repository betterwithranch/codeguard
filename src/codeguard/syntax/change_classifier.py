import tempfile
from dataclasses import dataclass
from pathlib import Path

from codeguard.syntax.parsed_file import ParsedFile
from codeguard.syntax.syntax_scanner import SyntaxScanner
from codeguard.working_tree import ChangedLines, WorkingTree


@dataclass(frozen=True)
class ChangeClassifier:
    scanner: SyntaxScanner
    working_tree: WorkingTree

    def classify(self, scope: ChangedLines) -> ChangedLines:
        head = self.scanner.scan_files(self.working_tree.root, scope.files)
        base = self._base(scope)
        return scope.with_node_starts(
            {file: parsed.enclosing_starts(scope.points(file)) for file, parsed in head.items()}
        ).with_kinds(
            {
                file: parsed.touched_kinds(scope.points(file), base.get(file))
                for file, parsed in head.items()
            }
        )

    def _base(self, scope: ChangedLines) -> dict[str, ParsedFile]:
        if scope.base is None:
            return {}
        contents = self.working_tree.base_contents(scope.base, scope.files)
        with tempfile.TemporaryDirectory() as directory:
            for file, content in contents.items():
                path = Path(directory) / file
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            return self.scanner.scan_files(Path(directory), list(contents))
