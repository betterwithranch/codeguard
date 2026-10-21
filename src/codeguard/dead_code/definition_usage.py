from dataclasses import dataclass
from typing import Self

from codeguard.review import Category, Diagnostic, Severity


@dataclass(frozen=True)
class DefinitionKey:
    file: str
    kind: str
    name: str


@dataclass(frozen=True)
class UnusedDefinition:
    key: DefinitionKey
    line: int

    def diagnostic(self, rule: str, severity: Severity) -> Diagnostic:
        return Diagnostic(
            rule=rule,
            file=self.key.file,
            line=self.line,
            message=f"Unused {self.key.kind} '{self.key.name}': the change removed its last use. "
            "Delete it.",
            severity=severity,
            note=None,
            category=Category.DEAD_CODE,
            confidence=1.0,
        )


@dataclass(frozen=True)
class DefinitionUsage:
    defined: frozenset[DefinitionKey]
    unused: tuple[UnusedDefinition, ...]

    def newly_unused(self, base: Self) -> tuple[UnusedDefinition, ...]:
        used_in_base = base.defined - {definition.key for definition in base.unused}
        return tuple(definition for definition in self.unused if definition.key in used_in_base)
