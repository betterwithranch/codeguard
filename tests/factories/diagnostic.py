import factory

from codeguard.review import Category, Diagnostic, ErrorType, Severity
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
            note=None,
            category=Category.JUDGED,
            end_line=None,
            confidence=1.0,
        )
        dead_code = factory.Trait(
            rule="no-dead-code",
            file="lib.py",
            message="Unused function 'helper': the change removed its last use. Delete it.",
            note=None,
            category=Category.DEAD_CODE,
            end_line=None,
        )
        judge_error = factory.Trait(
            rule=factory.LazyFunction(lambda: MakeSkill().name),
            line=None,
            message="The judge call failed, so this rule was not checked.",
            note="claude exited with 1.",
            category=Category.JUDGE_ERROR,
            confidence=0.0,
            error_type=ErrorType.PROCESS,
        )

    rule = "no-print"
    file = "a.py"
    line = 1
    message = "Use logging, not print."
    severity = Severity.ERROR
    note = "print bypasses log levels.\nCall logger.info instead.\n"
    category = Category.PATTERN
    confidence = 1.0
    error_type = None
    end_line = factory.SelfAttribute("line")


class MakeViolation(factory.Factory):
    class Meta:
        model = Violation

    file = "a.py"
    line = 1
    message = "Use logging, not print."
    confidence = 1.0
