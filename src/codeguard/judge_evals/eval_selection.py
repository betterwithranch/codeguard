from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class EvalSelection:
    rules: frozenset[str] = frozenset()
    cases: tuple[str, ...] = ()

    def selects_rule(self, rule: str) -> bool:
        return not self.rules or rule in self.rules

    def selects_case(self, case: str) -> bool:
        return not self.cases or any(text in case for text in self.cases)

    def problems(self, case_names: Mapping[str, Sequence[str]]) -> tuple[str, ...]:
        """Name each selector that matches nothing, given each judge rule's case names."""
        unknown = tuple(
            f"--rule {rule}: no judge rule {rule}"
            for rule in sorted(self.rules - case_names.keys())
        )
        selected = [
            case for rule, cases in case_names.items() if self.selects_rule(rule) for case in cases
        ]
        unmatched = tuple(
            f"--case {text}: no case of the selected rules has it in its name"
            for text in self.cases
            if not any(text in case for case in selected)
        )
        return unknown + unmatched
