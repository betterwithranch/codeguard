import factory

from codeguard.review import Confidence, Finding, Severity


class MakeFinding(factory.Factory):
    class Meta:
        model = Finding

    class Params:
        warning = factory.Trait(
            rule="no-breakpoint",
            message="Remove breakpoint().",
            severity=Severity.WARNING,
            note=None,
        )
        low_confidence = factory.Trait(confidence=Confidence.LOW)

    rule = "no-print"
    file = "a.py"
    line = 1
    message = "Use logging, not print."
    severity = Severity.ERROR
    note = "print bypasses log levels.\nCall logger.info instead.\n"
    confidence = Confidence.HIGH
