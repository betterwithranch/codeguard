from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from codeguard.ast_grep import AstGrep
from codeguard.config import Ruleset
from codeguard.pattern_rules.command import AstGrepCommand
from codeguard.pattern_rules.layout import Layout
from codeguard.pattern_rules.match import AstGrepMatch
from codeguard.review import Diagnostic


@dataclass(frozen=True)
class PatternRuleCheck:
    root: Path
    ruleset: Ruleset
    ast_grep: AstGrep = AstGrep()

    def check(self, files: Sequence[str]) -> list[Diagnostic]:
        if not files or not self._layout.has_rules():
            return []
        output = AstGrepCommand(self._layout).scan(files, self._options)
        matches = (AstGrepMatch.model_validate_json(line) for line in output.splitlines())
        return [
            match.diagnostic(self.ruleset.qualified_rule_id(match.rule_id))
            for match in matches
            if self._selected(match)
        ]

    @property
    def _layout(self) -> Layout:
        return Layout(self.root, self.ruleset.root, self.ast_grep)

    @property
    def _options(self) -> list[str]:
        selection = self.ruleset.selection
        ruleset_severity = [] if selection.severity is None else [f"--{selection.severity}"]
        candidates = (
            selection.exclude if selection.include is None else self.ruleset.pattern_rule_ids()
        )
        excluded = [f"--off={rule}" for rule in sorted(candidates) if selection.excludes(rule)]
        severities = [
            f"--{override.severity}={rule}"
            for rule, override in selection.rules.items()
            if override.severity is not None
        ]
        return [*ruleset_severity, *excluded, *severities]

    def _selected(self, match: AstGrepMatch) -> bool:
        return self.ruleset.pattern_scope(match.rule_id).matches(match.file)
