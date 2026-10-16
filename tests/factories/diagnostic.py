import factory
from factories.skill import MakeSkill

from codeguard.review import Confidence, Diagnostic, Severity
from codeguard.review.judge import Violation


class MakeDiagnostic(factory.Factory):
    class Meta:
        model = Diagnostic

    class Params:
        warning = factory.Trait(
            rule="no-breakpoint",
            message="Remove breakpoint().",
            severity=Severity.WARNING,
            note=None,
        )
        low_confidence = factory.Trait(confidence=Confidence.LOW)
        judged = factory.Trait(
            rule=factory.LazyFunction(lambda: MakeSkill().name),
            note="Call logger.info instead.",
        )

    rule = "no-print"
    file = "a.py"
    line = 1
    message = "Use logging, not print."
    severity = Severity.ERROR
    note = "print bypasses log levels.\nCall logger.info instead.\n"
    confidence = Confidence.HIGH


class MakeViolation(factory.Factory):
    class Meta:
        model = Violation

    file = "a.py"
    line = 1
    message = "Use logging, not print."
    note = "Call logger.info instead."
    confidence = Confidence.HIGH
