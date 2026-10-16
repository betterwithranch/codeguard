from dataclasses import dataclass

from codeguard.review import Verdict


@dataclass(frozen=True)
class JudgeCase:
    file: str
    violates: bool

    def problem(self, verdict: Verdict, confidence_threshold: float) -> str | None:
        found = [violation for violation in verdict.violations if violation.file == self.file]
        listed = "".join(
            f"\n  line {violation.line} ({violation.confidence:.2f}): {violation.message}"
            for violation in found
        )
        if not self.violates:
            return f"expected no violation, got:{listed}" if found else None
        if any(violation.confidence >= confidence_threshold for violation in found):
            return None
        if not found:
            return "expected a violation, got none"
        return f"expected a violation with confidence {confidence_threshold:.2f}, got:{listed}"
