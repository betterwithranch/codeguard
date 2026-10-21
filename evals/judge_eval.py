import argparse
import sys
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from threading import Semaphore

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import EqualsExpected

from codeguard.claude_provider import ClaudeJudge
from codeguard.config import SKILL_FILE
from codeguard.gemini_provider import GeminiJudge, gemini_client
from codeguard.review import Judge, JudgeRequest, Skill

_FIXTURES = Path(__file__).parent / "fixtures"
_MAX_CONCURRENCY = 4
_PROCESSES = Semaphore(_MAX_CONCURRENCY)
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


def violates(judge: Judge, case: JudgeCase) -> bool:
    skill = Skill.from_file(case.skill, _FIXTURES / "skills" / case.skill / SKILL_FILE)
    verdict = judge.judge(JudgeRequest(skill, case.file))
    return any(violation.file == case.file for violation in verdict.violations)


def passes(model: str, judge: Judge, repeat: int) -> bool:
    report = _DATASET.evaluate_sync(
        partial(violates, judge), task_name=model, repeat=repeat, max_concurrency=_MAX_CONCURRENCY
    )
    report.print(include_input=True, include_output=True)
    averages = report.averages()
    return not report.failures and averages is not None and averages.assertions == 1.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the judge against fixture skills.")
    parser.add_argument("--repeat", type=int, default=1, help="Runs per case. Default: 1.")
    parser.add_argument(
        "--gemini",
        metavar="MODEL",
        action="append",
        help="Evaluate this Gemini model on Google Cloud instead of the Claude models. Repeatable.",
    )
    args = parser.parse_args()
    judges = _gemini_judges(args.gemini) if args.gemini else _claude_judges()
    results = [passes(model, judge, args.repeat) for model, judge in judges.items()]
    return 0 if all(results) else 1


def _claude_judges() -> dict[str, Judge]:
    return {model: ClaudeJudge(_FIXTURES, model, _PROCESSES) for model in _MODELS}


def _gemini_judges(models: list[str]) -> dict[str, Judge]:
    client = gemini_client()
    return {model: GeminiJudge(_FIXTURES, model, client, _PROCESSES) for model in models}


if __name__ == "__main__":
    sys.exit(main())
