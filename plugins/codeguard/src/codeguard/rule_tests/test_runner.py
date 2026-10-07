from typing import Protocol

from codeguard.rule_tests.rule_test_result import RuleTestResult


class TestRunner(Protocol):
    def run(self) -> RuleTestResult: ...

    def update_snapshots(self) -> RuleTestResult: ...
