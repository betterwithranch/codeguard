from dataclasses import dataclass
from functools import cached_property
from threading import Semaphore

from codeguard.ast_grep import AstGrep
from codeguard.config import Config, ConfigLoader
from codeguard.judge_evals import EvalCoverage, JudgeEvalResult, JudgeEvalRunner
from codeguard.pattern_rules import Layout, PatternRuleCheck, PatternRuleTestRunner
from codeguard.review import (
    Bindings,
    CheckStep,
    Deadline,
    JudgeCheck,
    JudgePlan,
    JudgeRequest,
    PlannedCall,
    Review,
    Reviewer,
)
from codeguard.rule_tests import BroadTriggers, RuleEvalSchema, RuleTests, TriggerTestRunner
from codeguard.rules.judges import Judges
from codeguard.rules.ruleset_resolver import RulesetResolver
from codeguard.syntax import ChangeClassifier
from codeguard.working_tree import AllLines, ChangedLines, WorkingTree


@dataclass(frozen=True)
class Rules:
    working_tree: WorkingTree
    latest: bool = False

    @cached_property
    def config(self) -> Config:
        return ConfigLoader(self.working_tree.root).load()

    def review(self, scope: ChangedLines | AllLines) -> Review:
        deadline = Deadline(self.config.review_time_limit_minutes)
        classified = self._classified(scope)
        reviewer = Reviewer(
            steps=(
                self._pattern_step,
                CheckStep(checks=self._judge_checks(classified, deadline)),
            )
        )
        return reviewer.run(classified)

    def check_patterns(self, scope: ChangedLines | AllLines) -> Review:
        return Reviewer(steps=(self._pattern_step,)).run(scope)

    @property
    def _pattern_step(self) -> CheckStep:
        root = self.working_tree.root
        return CheckStep(
            checks=tuple(
                PatternRuleCheck(root, ruleset, self._ast_grep)
                for ruleset in self._resolver.rulesets
            )
        )

    def _classified(self, scope: ChangedLines | AllLines) -> ChangedLines | AllLines:
        if isinstance(scope, AllLines):
            return scope
        classifier = ChangeClassifier.for_rulesets(
            self._ast_grep, self._resolver.rulesets, self.working_tree
        )
        return classifier.classify(scope)

    def plan(self, scope: ChangedLines | AllLines) -> JudgePlan:
        root = self.working_tree.root
        classified = self._classified(scope)
        return JudgePlan(
            calls=tuple(
                PlannedCall(
                    rule=binding.rule,
                    file=file,
                    cached=self._judges.cached(root, binding.model).has(
                        JudgeRequest(binding.skill, file)
                    ),
                    triggered=binding.is_triggered(classified, file),
                )
                for binding in Bindings.from_rulesets(self._resolver.rulesets)
                for file in binding.files(classified.files)
            )
        )

    @property
    def tests(self) -> RuleTests:
        root = self.working_tree.root
        loaders = self._resolver.own_rulesets
        return RuleTests(
            snapshot_runners=[
                runner
                for loader in loaders
                for runner in (
                    PatternRuleTestRunner(Layout(root, loader.root, self._ast_grep)),
                    RuleEvalSchema(root, loader.root),
                )
            ],
            runners=[
                runner
                for loader in loaders
                for runner in (
                    BroadTriggers(loader),
                    TriggerTestRunner(root, loader, self._ast_grep),
                )
            ],
        )

    def evaluate(self, repeat: int = 1) -> JudgeEvalResult:
        root = self.working_tree.root
        threshold = self.config.confidence_threshold
        judges = self._judges
        # A repeat has to call the model again to show whether the verdict is stable.
        judge = judges.cached if repeat == 1 else judges.uncached
        return JudgeEvalResult.merge(
            JudgeEvalResult.merge(
                (
                    JudgeEvalRunner(
                        root, loader, judge, threshold, repeat, self.config.judge, self._ast_grep
                    ).run(),
                    JudgeEvalResult(checks=EvalCoverage(loader).run()),
                )
            )
            for loader in self._resolver.own_rulesets
        )

    @cached_property
    def _ast_grep(self) -> AstGrep:
        ast_grep = AstGrep(self.config.ast_grep)
        ast_grep.check_supported()
        return ast_grep

    @cached_property
    def _resolver(self) -> RulesetResolver:
        return RulesetResolver(
            self.working_tree.root, self.config, self._ast_grep, latest=self.latest
        )

    @cached_property
    def _judges(self) -> Judges:
        judge = self.config.judge
        return Judges(judge, processes=Semaphore(judge.concurrency))

    def _judge_checks(
        self, scope: ChangedLines | AllLines, deadline: Deadline
    ) -> tuple[JudgeCheck, ...]:
        root = self.working_tree.root
        threshold = self.config.confidence_threshold
        return tuple(
            JudgeCheck(
                binding, self._judges.cached(root, binding.model, deadline), threshold, scope
            )
            for binding in Bindings.from_rulesets(self._resolver.rulesets)
        )
