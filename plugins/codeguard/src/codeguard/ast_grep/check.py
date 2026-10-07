import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from codeguard.ast_grep.command import AstGrepCommand
from codeguard.ast_grep.layout import Layout
from codeguard.review import Finding, Severity


@dataclass(frozen=True)
class AstGrepCheck:
    layout: Layout

    def check(self, files: Sequence[str]) -> list[Finding]:
        if not files or not self.layout.has_rules():
            return []
        output = self._command.scan(files)
        return [_finding(json.loads(line)) for line in output.splitlines()]

    @property
    def _command(self) -> AstGrepCommand:
        return AstGrepCommand(self.layout)


def _finding(match: dict[str, Any]) -> Finding:
    return Finding(
        rule=match["ruleId"],
        file=match["file"],
        line=match["range"]["start"]["line"] + 1,
        message=match["message"],
        severity=Severity(match["severity"]),
        note=match["note"],
    )
