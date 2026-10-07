from collections.abc import Sequence
from dataclasses import dataclass

from codeguard.ast_grep import AstGrepCheck, AstGrepTestRunner, Layout
from codeguard.checkout import Checkout
from codeguard.review import Review
from codeguard.rule_tests import RuleTests


@dataclass(frozen=True)
class Rules:
    checkout: Checkout

    def review(self, files: Sequence[str]) -> Review:
        return Review.run([AstGrepCheck(self._layout)], files)

    @property
    def tests(self) -> RuleTests:
        return RuleTests(runners=[AstGrepTestRunner(self._layout)])

    @property
    def _layout(self) -> Layout:
        return Layout(self.checkout.root)
