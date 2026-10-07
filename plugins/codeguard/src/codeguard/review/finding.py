import hashlib
import textwrap
from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    HINT = "hint"


@dataclass(frozen=True)
class Finding:
    rule: str
    file: str
    line: int
    message: str
    severity: Severity
    note: str | None

    @property
    def id(self) -> str:
        key = f"{self.rule}:{self.file}:{self.line}"
        return hashlib.sha256(key.encode()).hexdigest()[:12]

    def __str__(self) -> str:
        summary = f"{self.file}:{self.line}: {self.severity} {self.rule}: {self.message} [{self.id}]"
        if self.note is None:
            return summary
        return f"{summary}\n{textwrap.indent(self.note.rstrip(), '  ')}"
