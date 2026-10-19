import hashlib
import textwrap

from pydantic import BaseModel, ConfigDict

from codeguard.config import Severity


class Diagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule: str
    file: str
    line: int | None
    message: str
    severity: Severity
    note: str | None

    @property
    def id(self) -> str:
        key = f"{self.rule}:{self.file}:{self.line}"
        return hashlib.sha256(key.encode()).hexdigest()[:12]

    @property
    def blocks(self) -> bool:
        return self.severity is Severity.ERROR

    def __str__(self) -> str:
        location = self.file if self.line is None else f"{self.file}:{self.line}"
        summary = f"{location}: {self.severity} {self.rule}: {self.message} [{self.id}]"
        if self.note is None:
            return summary
        return f"{summary}\n{textwrap.indent(self.note.rstrip(), '  ')}"
