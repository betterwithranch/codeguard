from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property

from codeguard.ast_grep import AstGrepCheck, AstGrepTestRunner, Layout
from codeguard.checkout import Checkout
from codeguard.claude import ClaudeJudge
from codeguard.config import Config, ConfigLoader
from codeguard.review import CheckStage, JudgeStage, Review, Reviewer
from codeguard.rule_tests import RuleTests


@dataclass(frozen=True)
class Rules:
    checkout: Checkout

    @cached_property
    def config(self) -> Config:
        return ConfigLoader(self.checkout.root).load()

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
