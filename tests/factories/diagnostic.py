import factory

from codeguard.review import Diagnostic, Severity
from codeguard.review.judge import Violation
from factories.skill import MakeSkill


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
        judged = factory.Trait(
            rule=factory.LazyFunction(lambda: MakeSkill().name),
            note="Call logger.info instead.",
            end_line=None,
        )

    rule = "no-print"
    file = "a.py"
    line = 1
    message = "Use logging, not print."
    severity = Severity.ERROR
    note = "print bypasses log levels.\nCall logger.info instead.\n"
    end_line = factory.SelfAttribute("line")


class MakeViolation(factory.Factory):
    class Meta:
        model = Violation

    file = "a.py"
    line = 1
    message = "Use logging, not print."
    note = "Call logger.info instead."
    confidence = 1.0
