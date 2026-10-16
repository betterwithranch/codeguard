from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from diskcache import Cache

from codeguard.ast_grep import AstGrepCheck, AstGrepTestRunner, Layout
from codeguard.claude import ClaudeJudge
from codeguard.config import Config, ConfigLoader
from codeguard.review import Bindings, CachedJudge, CheckStep, JudgeCheck, Review, Reviewer
from codeguard.rule_tests import RuleTests
from codeguard.working_tree import WorkingTree

_JUDGEMENT_CACHE_DIR = Path.home() / ".cache" / "codeguard" / "judgements"


@dataclass(frozen=True)
class Rules:
    working_tree: WorkingTree

    @cached_property
    def config(self) -> Config:
        return ConfigLoader(self.working_tree.root).load()

    def review(self, files: Sequence[str]) -> Review:
        reviewer = Reviewer(
            steps=(
                CheckStep(checks=(AstGrepCheck(self._layout),)),
                CheckStep(checks=self._judge_checks),
            )
        )
        return reviewer.run(files)

    @property
    def tests(self) -> RuleTests:
        return RuleTests(runners=[AstGrepTestRunner(self._layout)])

    @property
    def _judge_checks(self) -> tuple[JudgeCheck, ...]:
        root = self.working_tree.root
        judge = CachedJudge(wrapped=ClaudeJudge(root), store=Cache(_JUDGEMENT_CACHE_DIR), root=root)
        bindings = Bindings.from_config(self.config.bindings)
        return tuple(JudgeCheck(binding, judge) for binding in bindings)

    @property
    def _layout(self) -> Layout:
        return Layout(self.working_tree.root)
