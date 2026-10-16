import argparse
import sys
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import EqualsExpected

from codeguard.claude import ClaudeJudge
from codeguard.config import SKILL_FILE
from codeguard.review import JudgeRequest, Skill

_FIXTURES = Path(__file__).parent / "fixtures"
_MAX_CONCURRENCY = 4
_MODELS = ("claude-haiku-5-5", "claude-sonnet-5-5")


@dataclass(frozen=True)
class JudgeCase:
    skill: str
    file: str


_DATASET = Dataset[JudgeCase, bool, None](
    name="judge",
    cases=[
        Case(
            name="recomputes another type's data",
            inputs=JudgeCase("responsibility-placement", "orders/invoice.py"),
            expected_output=True,
        ),
        Case(
            name="calls the type's method",
            inputs=JudgeCase("responsibility-placement", "orders/receipt.py"),
            expected_output=False,
        ),
        Case(
            name="discards an exception",
            inputs=JudgeCase("exception-handling", "payments/charge.py"),
            expected_output=True,
        ),
        Case(
            name="logs and re-raises an exception",
            inputs=JudgeCase("exception-handling", "payments/refund.py"),
            expected_output=False,
        ),
    ],
    evaluators=[EqualsExpected()],
)


def violates(model: str, case: JudgeCase) -> bool:
    skill = Skill.from_file(case.skill, _FIXTURES / "skills" / case.skill / SKILL_FILE)
    verdict = ClaudeJudge(_FIXTURES, model).judge(JudgeRequest(skill, case.file))
    return any(violation.file == case.file for violation in verdict.violations)


def passes(model: str, repeat: int) -> bool:
    report = _DATASET.evaluate_sync(
        partial(violates, model), task_name=model, repeat=repeat, max_concurrency=_MAX_CONCURRENCY
    )
    report.print(include_input=True, include_output=True)
    averages = report.averages()
    return averages is not None and averages.assertions == 1.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the judge against fixture skills.")
    parser.add_argument("--repeat", type=int, default=1, help="Runs per case. Default: 1.")
    args = parser.parse_args()
    results = [passes(model, args.repeat) for model in _MODELS]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
