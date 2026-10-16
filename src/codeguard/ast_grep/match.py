from pathlib import PurePath

from pydantic import BaseModel, ConfigDict, Field

from codeguard.review import Diagnostic, Severity


class _Position(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    line: int


class _Range(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    start: _Position


class AstGrepMatch(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    rule_id: str = Field(alias="ruleId")
    file: str
    range: _Range
    message: str
    severity: Severity
    note: str | None

    def in_paths(self, paths: tuple[str, ...]) -> bool:
        return any(PurePath(self.file).full_match(pattern) for pattern in paths)

    def diagnostic(self, rule: str) -> Diagnostic:
        return Diagnostic(
            rule=rule,
            file=self.file,
            line=self.range.start.line + 1,
            message=self.message,
            severity=self.severity,
            note=self.note,
        )
