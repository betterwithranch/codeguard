from collections.abc import Mapping, Sequence
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
        rules = self.ruleset.dead_code_rules()
        if not rules:
            return []
        before = self.working_tree.committed_files(self.base, VultureEngine.suffix)
        after = self.working_tree.current_files(VultureEngine.suffix)
        if before == after:
            return []
        after = _unparsed_as_before(VultureEngine(), before, after)
        return [
            diagnostic for rule in rules for diagnostic in self._diagnostics(rule, before, after)
        ]

    def _diagnostics(
        self, rule: DeadCodeRule, before: Mapping[str, bytes], after: Mapping[str, bytes]
    ) -> list[Diagnostic]:
        engine = VultureEngine(rule.whitelist)
        with ProcessPoolExecutor(max_workers=2, mp_context=get_context("spawn")) as executor:
            base_usage, usage = executor.map(engine.usage, (before, after))
        scope = self.ruleset.dead_code_scope(rule.id)
        return [
            definition.diagnostic(self.ruleset.qualified_rule_id(rule.id), rule.severity)
            for definition in usage.newly_unused(base_usage)
            if scope.matches(definition.key.file)
        ]


def _unparsed_as_before(
    engine: VultureEngine, before: Mapping[str, bytes], after: Mapping[str, bytes]
) -> dict[str, bytes]:
    parsed = {
        file: content
        for file, content in after.items()
        if before.get(file) == content or engine.parses(content)
    }
    unparsed = {file: before[file] for file in after.keys() - parsed.keys() if file in before}
    return {**parsed, **unparsed}
