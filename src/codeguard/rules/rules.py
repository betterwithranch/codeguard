import os
from dataclasses import dataclass
from functools import cached_property
from importlib.metadata import version
from pathlib import Path
from threading import Semaphore

from diskcache import Cache
from packaging.version import Version

from codeguard.ast_grep import AstGrep
from codeguard.claude_provider import ClaudeJudge, Deadline, PromptCacheWarmup
from codeguard.config import Config, ConfigError, ConfigLoader, Lock, Ruleset, RulesetLoader
from codeguard.judge_evals import JudgeEvalRunner, RulePackageReview
from codeguard.packages import (
    MANIFEST_FILE,
    GitFetch,
    LatestRefs,
    LockedRefs,
    Manifest,
    Packages,
)
from codeguard.pattern_rules import Layout, PatternRuleCheck, PatternRuleTestRunner
from codeguard.review import (
    Bindings,
    CachedJudge,
    CheckStep,
    Judge,
    JudgeCheck,
    JudgePlan,
    JudgeRequest,
    PlannedCall,
    Review,
    Reviewer,
)
from codeguard.rule_tests import BroadTriggers, RuleTestResult, RuleTests, TriggerTestRunner
from codeguard.syntax import ChangeClassifier
from codeguard.working_tree import AllLines, ChangedLines, WorkingTree

_CACHE_DIR = Path.home() / ".cache" / "codeguard"
_JUDGEMENT_CACHE_DIR = _CACHE_DIR / "judgements"
_PACKAGE_CACHE_DIR = _CACHE_DIR / "packages"
_CODEGUARD_VERSION = Version(version("codeguard"))


@dataclass(frozen=True)
class Rules:
    working_tree: WorkingTree
    latest: bool = False

    @cached_property
    def config(self) -> Config:
        return ConfigLoader(self.working_tree.root).load()

    def review(self, scope: ChangedLines | AllLines) -> Review:
        root = self.working_tree.root
        deadline = Deadline(self.config.review_time_limit_minutes)
        classified = self._classified(scope)
        reviewer = Reviewer(
            steps=(
                CheckStep(
                    checks=tuple(
                        PatternRuleCheck(root, ruleset, self._ast_grep)
                        for ruleset in self._rulesets
                    )
                ),
                CheckStep(checks=self._judge_checks(classified, deadline)),
            )
        )
        return reviewer.run(classified)

    def _classified(self, scope: ChangedLines | AllLines) -> ChangedLines | AllLines:
        if isinstance(scope, AllLines):
            return scope
        classifier = ChangeClassifier.for_rulesets(
            self._ast_grep, self._rulesets, self.working_tree
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
                    cached=self._judge(root, binding.model).has(JudgeRequest(binding.skill, file)),
                    triggered=binding.is_triggered(classified, file),
                )
                for binding in Bindings.from_rulesets(self._rulesets)
                for file in binding.files(classified.files)
            )
        )

    @property
    def tests(self) -> RuleTests:
        root = self.working_tree.root
        loaders = self._own_rulesets
        return RuleTests(
            snapshot_runners=[
                runner
                for loader in loaders
                for runner in (
                    PatternRuleTestRunner(Layout(root, loader.root, self._ast_grep)),
                    PatternRuleTestRunner(Layout.gates(root, loader.root, self._ast_grep)),
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

    def evaluate(self, repeat: int = 1) -> RuleTestResult:
        root = self.working_tree.root
        threshold = self.config.confidence_threshold
        runs = (self._judge, *(self._uncached_judge for _ in range(repeat - 1)))
        return RuleTestResult.merge(
            result
            for loader in self._own_rulesets
            for result in (
                JudgeEvalRunner(root, loader, runs, threshold, self._ast_grep).run(),
                RulePackageReview(loader, self._judge, threshold).run(),
            )
        )

    @cached_property
    def _rulesets(self) -> tuple[Ruleset, ...]:
        root = self.working_tree.root
        refs = LatestRefs() if self.latest else LockedRefs(Lock.load(root))
        packages = Packages(
            root, GitFetch(_PACKAGE_CACHE_DIR), self._ast_grep.version, _CODEGUARD_VERSION, refs
        )
        return (RulesetLoader.local(root).load(), *packages.rulesets(self.config.packages))

    @cached_property
    def _ast_grep(self) -> AstGrep:
        ast_grep = AstGrep(self.config.ast_grep)
        ast_grep.check_supported()
        return ast_grep

    @cached_property
    def _own_rulesets(self) -> list[RulesetLoader]:
        root = self.working_tree.root
        manifest = Manifest.in_repo(root)
        loaders = [RulesetLoader.local(root)]
        if manifest:
            for problem in (
                manifest.codeguard_problem(_CODEGUARD_VERSION),
                manifest.ast_grep_problem(self._ast_grep.version),
            ):
                if problem:
                    raise ConfigError(f"{root / MANIFEST_FILE} is invalid:\n  {problem}")
            loaders.extend(
                RulesetLoader(repo=root, root=root / name, name=f"{manifest.name}/{name}")
                for name in manifest.rulesets
            )
        for loader in loaders:
            loader.check()
        return loaders

    @cached_property
    def _store(self) -> Cache:
        return Cache(_JUDGEMENT_CACHE_DIR)

    @cached_property
    def _judge_processes(self) -> Semaphore:
        return Semaphore(os.process_cpu_count() or 1)

    def _judge(self, root: Path, model: str, deadline: Deadline | None = None) -> CachedJudge:
        return CachedJudge(self._uncached_judge(root, model, deadline), self._store, root)

    @cached_property
    def _warmup(self) -> PromptCacheWarmup:
        return PromptCacheWarmup()

    def _uncached_judge(self, root: Path, model: str, deadline: Deadline | None = None) -> Judge:
        return ClaudeJudge(
            root, model, self._judge_processes, warmup=self._warmup, deadline=deadline
        )

    def _judge_checks(
        self, scope: ChangedLines | AllLines, deadline: Deadline
    ) -> tuple[JudgeCheck, ...]:
        root = self.working_tree.root
        threshold = self.config.confidence_threshold
        return tuple(
            JudgeCheck(binding, self._judge(root, binding.model, deadline), threshold, scope)
            for binding in Bindings.from_rulesets(self._rulesets)
        )
