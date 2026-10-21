from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing import get_context

from codeguard.config import DeadCodeRule, Ruleset
from codeguard.dead_code.vulture_engine import VultureEngine
from codeguard.review import Diagnostic
from codeguard.working_tree import WorkingTree


@dataclass(frozen=True)
class DeadCodeCheck:
    working_tree: WorkingTree
    ruleset: Ruleset
    base: str

    def check(self, files: Sequence[str]) -> list[Diagnostic]:
        return [
            diagnostic
            for rule in self.ruleset.dead_code_rules()
            for diagnostic in self._diagnostics(rule)
        ]

    def _diagnostics(self, rule: DeadCodeRule) -> list[Diagnostic]:
        engine = VultureEngine(rule.whitelist)
        before = self.working_tree.committed_files(self.base, engine.suffix)
        after = self.working_tree.current_files(engine.suffix)
        if before == after:
            return []
        with ProcessPoolExecutor(max_workers=2, mp_context=get_context("spawn")) as executor:
            base_usage, usage = executor.map(engine.usage, (before, after))
        scope = self.ruleset.dead_code_scope(rule.id)
        return [
            definition.diagnostic(self.ruleset.qualified_rule_id(rule.id), rule.severity)
            for definition in usage.newly_unused(base_usage)
            if scope.matches(definition.key.file)
        ]
