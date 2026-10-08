from collections.abc import Sequence
from dataclasses import dataclass
from typing import Self

from codeguard.ast_grep import AstGrepCheck, AstGrepTestRunner, Layout
from codeguard.checkout import Checkout
from codeguard.claude import ClaudeJudge
from codeguard.config import Config, ConfigLoader
from codeguard.review import CheckStage, JudgeStage, Review, Reviewer
from codeguard.rule_tests import RuleTests


@dataclass(frozen=True)
class Rules:
    checkout: Checkout
    config: Config

    @classmethod
    def load(cls, checkout: Checkout) -> Self:
        return cls(checkout=checkout, config=ConfigLoader(checkout.root).load())

    def review(self, files: Sequence[str]) -> Review:
        reviewer = Reviewer(
            stages=(
                CheckStage(checks=(AstGrepCheck(self._layout),)),
                JudgeStage(judge=ClaudeJudge(self.checkout.root), selector=self.config),
            )
        )
        return reviewer.run(files)

    @property
    def tests(self) -> RuleTests:
        return RuleTests(runners=[AstGrepTestRunner(self._layout)])

    @property
    def _layout(self) -> Layout:
        return Layout(self.checkout.root)
