from dataclasses import dataclass

from codeguard.ast_grep.command import AstGrepCommand
from codeguard.ast_grep.layout import Layout
from codeguard.ast_grep.snapshots import Snapshots
from codeguard.rule_tests import RuleTestResult

NO_TESTS = RuleTestResult(failed=False)


@dataclass(frozen=True)
class AstGrepTestRunner:
    layout: Layout

    def run(self) -> RuleTestResult:
        if not self.layout.has_tests():
            return NO_TESTS
        stale = Snapshots.load(self.layout.test_dir).stale()
        if stale:
            return RuleTestResult(
                failed=False,
                problems=tuple(snapshot.stale_problem(self.layout.root) for snapshot in stale),
            )
        return RuleTestResult(failed=not self._command.test())

    def update_snapshots(self) -> RuleTestResult:
        if not self.layout.has_tests():
            return NO_TESTS
        for snapshot in Snapshots.load(self.layout.test_dir).stale():
            snapshot.path.unlink()
        return RuleTestResult(failed=not self._command.update_snapshots())

    @property
    def _command(self) -> AstGrepCommand:
        return AstGrepCommand(self.layout)
