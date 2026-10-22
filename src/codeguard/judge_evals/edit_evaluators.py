from dataclasses import dataclass

from pydantic.main import IncEx
from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext

from codeguard.config import ChangeKind
from codeguard.rule_tests import EditCase, EditReview, Outcome


@dataclass
class PartialEqualsExpected(Evaluator[EditCase, EditReview, None]):
    def evaluate(
        self, ctx: EvaluatorContext[EditCase, EditReview, None]
    ) -> EvaluationReason | dict[str, bool]:
        if ctx.expected_output is None:
            return {}
        fields = _listed_fields(ctx.expected_output)
        expected = ctx.expected_output.model_dump(mode="json", include=fields)
        actual = ctx.output.model_dump(mode="json", include=fields)
        if actual == expected:
            return EvaluationReason(value=True)
        return EvaluationReason(
            value=False,
            reason=f"expected {_described(expected)}, got {_described(actual)}{ctx.output.listing}",
        )


@dataclass
class ViolationsOnTriggers(Evaluator[EditCase, EditReview, None]):
    triggers: tuple[str, ...]
    confidence_threshold: float

    def evaluate(
        self, ctx: EvaluatorContext[EditCase, EditReview, None]
    ) -> EvaluationReason | dict[str, bool]:
        expected = ctx.expected_output.outcome if ctx.expected_output else None
        if (
            expected is not Outcome.INVALID
            or ctx.output.outcome is not Outcome.INVALID
            or ChangeKind.ANY in self.triggers
        ):
            return {}
        kinds = {
            violation.line: violation.kinds
            for violation in ctx.output.violations
            if violation.confidence >= self.confidence_threshold and violation.kinds is not None
        }
        if not kinds or any(set(self.triggers) & set(found) for found in kinds.values()):
            return EvaluationReason(value=True)
        lines = ", ".join(map(str, sorted(kinds)))
        on_lines = ", ".join(sorted({kind for found in kinds.values() for kind in found}))
        return EvaluationReason(
            value=False,
            reason=f"violation on line {lines} is outside the triggers {', '.join(self.triggers)}\n"
            f"  Add one of the kinds on that line to triggers in its binding: {on_lines}",
        )


def _described(fields: dict[str, object]) -> str:
    return ", ".join(f"{name} {value}" for name, value in fields.items())


def _listed_fields(review: EditReview) -> IncEx:
    fields: dict[str, IncEx | bool] = dict.fromkeys(review.model_fields_set, True)
    if "violations" in fields:
        listed = {name for violation in review.violations for name in violation.model_fields_set}
        fields["violations"] = {"__all__": listed}
    return fields
