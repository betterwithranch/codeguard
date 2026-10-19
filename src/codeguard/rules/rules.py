import os
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from threading import Semaphore

from diskcache import Cache

from codeguard.ast_grep import AstGrep
from codeguard.claude_provider import ClaudeJudge, Deadline, PromptCacheWarmup
from codeguard.config import Config, ConfigError, ConfigLoader, Lock, Ruleset, RulesetLoader
from codeguard.judge_evals import EvalResult, JudgeEvalRunner
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
from codeguard.rule_tests import RuleTests
from codeguard.syntax import SyntaxScanner
from codeguard.working_tree import AllLines, ChangedLines, WorkingTree

_CACHE_DIR = Path.home() / ".cache" / "codeguard"
_JUDGEMENT_CACHE_DIR = _CACHE_DIR / "judgements"
_PACKAGE_CACHE_DIR = _CACHE_DIR / "packages"


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
        reviewer = Reviewer(
            steps=(
                CheckStep(
                    checks=tuple(
                        PatternRuleCheck(root, ruleset, self._ast_grep)
                        for ruleset in self._rulesets
                    )
                ),
                CheckStep(checks=self._judge_checks(deadline)),
            )
        )
        return reviewer.run(self._with_enclosing_nodes(scope))

    def _with_enclosing_nodes(self, scope: ChangedLines | AllLines) -> ChangedLines | AllLines:
        if isinstance(scope, AllLines):
            return scope
        parsed = SyntaxScanner(self._ast_grep).scan_files(self.working_tree.root, scope.files)
        return scope.with_node_starts(
            {file: content.enclosing_starts(scope.points(file)) for file, content in parsed.items()}
        )

    def plan(self, scope: ChangedLines | AllLines) -> JudgePlan:
        root = self.working_tree.root
        return JudgePlan(
            calls=tuple(
                PlannedCall(
                    rule=binding.rule,
                    file=file,
                    cached=self._judge(root, binding.model).has(JudgeRequest(binding.skill, file)),
                )
                for binding in Bindings.from_rulesets(self._rulesets)
                for file in binding.files(scope.files)
            )
        )

    @property
    def tests(self) -> RuleTests:
        root = self.working_tree.root
        return RuleTests(
            runners=[
                PatternRuleTestRunner(Layout(root, loader.root, self._ast_grep))
                for loader in self._own_rulesets
            ]
        )

    def evaluate(self, repeat: int = 1) -> EvalResult:
        root = self.working_tree.root
        threshold = self.config.confidence_threshold
        runs = (self._judge, *(self._uncached_judge for _ in range(repeat - 1)))
        return EvalResult.merge(
            JudgeEvalRunner(root, loader, runs, threshold, self._ast_grep).run()
            for loader in self._own_rulesets
        )

    @cached_property
    def _rulesets(self) -> tuple[Ruleset, ...]:
        root = self.working_tree.root
        refs = LatestRefs() if self.latest else LockedRefs(Lock.load(root))
        packages = Packages(root, GitFetch(_PACKAGE_CACHE_DIR), self._ast_grep.version, refs)
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
            ast_grep_problem = manifest.ast_grep_problem(self._ast_grep.version)
            if ast_grep_problem:
                raise ConfigError(f"{root / MANIFEST_FILE} is invalid:\n  {ast_grep_problem}")
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

    def _judge_checks(self, deadline: Deadline) -> tuple[JudgeCheck, ...]:
        root = self.working_tree.root
        threshold = self.config.confidence_threshold
        return tuple(
            JudgeCheck(binding, self._judge(root, binding.model, deadline), threshold)
            for binding in Bindings.from_rulesets(self._rulesets)
        )
