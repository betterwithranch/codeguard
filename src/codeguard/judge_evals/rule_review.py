import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from codeguard.config import ChangeKind, GateRule
from codeguard.judge_evals.judge_factory import JudgeFactory
from codeguard.review import Binding, JudgeRequest, Skill
from codeguard.syntax import SyntaxTable

_RULE_FILE = "rule.md"
_DERIVED_KINDS = {
    ChangeKind.DEFINITION_ADDED_OR_REMOVED: (
        "the name line of a function or class, and every line of a file whose change adds, "
        "removes or renames a function or class"
    ),
    ChangeKind.CODE: "every line that is not only a comment or docstring",
    ChangeKind.ANY: "every changed line",
}
_SKILL = Skill(name="rule-review", text=(Path(__file__).parent / "rule_review.md").read_text())


@dataclass(frozen=True)
class RuleReview:
    binding: Binding
    gates: Mapping[str, GateRule]

    def problems(self, judges: JudgeFactory, confidence_threshold: float) -> list[str]:
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / _RULE_FILE).write_text(self._description())
            judge = judges(Path(directory), self.binding.model)
            verdict = judge.judge(JudgeRequest(_SKILL, _RULE_FILE))
        return [
            f"{self.binding.skill.name}: {violation.message}\n  {violation.note}"
            for violation in verdict.violations
            if violation.file == _RULE_FILE and violation.confidence >= confidence_threshold
        ]

    def _description(self) -> str:
        triggers = sorted(self.binding.triggers)
        other_gates = {
            gate: rule.rule for gate, rule in sorted(self.gates.items()) if gate not in triggers
        }
        other_kinds = [kind for kind in ChangeKind if kind not in triggers]
        return (
            f"# Rule: {self.binding.skill.name}\n\n"
            f"## Skill\n\n{self.binding.skill.text.strip()}\n\n"
            f"## Triggers\n\n{''.join(self._trigger(trigger) for trigger in triggers)}"
            f"## Other gates\n\n{_rules(other_gates) if other_gates else 'none'}\n\n"
            f"## Other change kinds\n\n{', '.join(other_kinds)}\n"
        )

    def _trigger(self, trigger: str) -> str:
        return f"### {trigger}\n\n{self._definition(trigger)}\n\n"

    def _definition(self, trigger: str) -> str:
        if trigger in self.gates:
            return f"A gate. Its ast-grep rule:\n\n`{_flow(self.gates[trigger].rule)}`"
        kind = ChangeKind(trigger)
        if kind in _DERIVED_KINDS:
            return f"A built-in change kind. It matches {_DERIVED_KINDS[kind]}."
        rules = {table.language: table.change_kinds[kind] for table in SyntaxTable.supported()}
        return f"A built-in change kind. Its ast-grep rule by language:\n\n{_rules(rules)}"


def _rules(rules: Mapping[str, object]) -> str:
    return "\n".join(f"- {name}: `{_flow(rule)}`" for name, rule in rules.items())


def _flow(rule: object) -> str:
    return yaml.safe_dump(rule, default_flow_style=True, width=1_000_000).strip()
