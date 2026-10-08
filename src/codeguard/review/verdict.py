from pydantic import BaseModel, ConfigDict

from codeguard.review.concern import Concern
from codeguard.review.finding import Confidence, Finding, Severity


class JudgedFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    file: str
    line: int
    message: str
    confidence: Confidence

    def finding(self, rule: str) -> Finding:
        return Finding(
            rule=rule,
            file=self.file,
            line=self.line,
            message=self.message,
            severity=Severity.ERROR,
            note=None,
            confidence=self.confidence,
        )


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    findings: tuple[JudgedFinding, ...]

    def findings_for(self, concern: Concern) -> list[Finding]:
        return [judged.finding(concern.skill.name) for judged in self.findings]
