from collections.abc import Iterable
from dataclasses import dataclass
from typing import Self, TextIO

from pydantic_evals.reporting import EvaluationReport
from rich.console import Console

from codeguard.rule_tests import EditCase, EditReview, RuleTestResult

type RuleEvalReport = EvaluationReport[EditCase, EditReview, None]


@dataclass(frozen=True)
class JudgeEvalResult:
    reports: tuple[RuleEvalReport, ...] = ()
    checks: RuleTestResult = RuleTestResult()

    @classmethod
    def merge(cls, results: Iterable[Self]) -> Self:
        collected = list(results)
        return cls(
            reports=tuple(report for result in collected for report in result.reports),
            checks=RuleTestResult.merge(result.checks for result in collected),
        )

    @property
    def passed(self) -> bool:
        return self.checks.passed and all(_passed(report) for report in self.reports)

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(failure for report in self.reports for failure in _failures(report))

    def write(self, out: TextIO) -> None:
        console = Console(file=out)
        for report in self.reports:
            report.print(console=console, include_reasons=True)
        for failure in self.failures:
            print(failure, file=out)
        self.checks.write(out)


def _passed(report: RuleEvalReport) -> bool:
    averages = report.averages()
    return (
        not report.failures
        and not any(case.evaluator_failures for case in report.cases)
        and averages is not None
        and averages.assertions == 1.0
    )


def _failures(report: RuleEvalReport) -> list[str]:
    rule = report.dataset_name
    failed = [
        f"{rule} {case.name}: {result.reason}"
        for case in report.cases
        for result in case.assertions.values()
        if not result.value
    ]
    not_evaluated = [
        f"{rule} {case.name}: {failure.name} failed: {failure.error_message}"
        for case in report.cases
        for failure in case.evaluator_failures
    ]
    not_judged = [
        f"{rule} {failure.name}: not judged: {failure.error_message}" for failure in report.failures
    ]
    return failed + not_evaluated + not_judged
