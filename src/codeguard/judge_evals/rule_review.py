import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from codeguard.config import ChangeKind, GateRule
from codeguard.judge_evals.judge_factory import JudgeFactory
from codeguard.review import Binding, JudgeRequest, Skill

_RULE_FILE = "rule.md"
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
            f"{self.binding.skill.name}: {violation.message}"
            for violation in verdict.violations
            if violation.file == _RULE_FILE and violation.confidence >= confidence_threshold
        ]

    def _description(self) -> str:
        gates = {gate: rule.rule for gate, rule in sorted(self.gates.items())}
        return (
            f"# Skill: {self.binding.skill.name}\n\n{self.binding.skill.text}\n"
            f"# Triggers\n\n{', '.join(sorted(self.binding.triggers))}\n\n"
            f"# Built-in change kinds\n\n{', '.join(ChangeKind)}\n\n"
            f"# Gates\n\n{yaml.safe_dump(gates, sort_keys=True) if gates else 'none'}\n"
        )
