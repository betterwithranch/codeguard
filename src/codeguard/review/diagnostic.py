import hashlib
import textwrap
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


class Confidence(StrEnum):
    HIGH = "high"
    LOW = "low"


class Diagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule: str
    file: str
    line: int
    message: str
    severity: Severity
    note: str | None
    confidence: Confidence

    @property
    def id(self) -> str:
        key = f"{self.rule}:{self.file}:{self.line}"
        return hashlib.sha256(key.encode()).hexdigest()[:12]

    @property
    def blocks(self) -> bool:
        return self.severity is Severity.ERROR and self.confidence is Confidence.HIGH

    def __str__(self) -> str:
        location = f"{self.file}:{self.line}"
        summary = f"{location}: {self.severity} {self.rule}: {self.message} [{self.id}]"
        if self.note is None:
            return summary
        return f"{summary}\n{textwrap.indent(self.note.rstrip(), '  ')}"
