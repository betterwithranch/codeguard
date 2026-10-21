from dataclasses import dataclass
from pathlib import Path
from typing import Self

from pydantic import ValidationError
from pydantic_core import ErrorDetails


class ConfigError(Exception):
    @classmethod
    def invalid(cls, location: Path, error: ValidationError, prefix: str | None = None) -> Self:
        problems = (
            _Problem.from_details(details, prefix) for details in error.errors(include_url=False)
        )
        return cls(f"{location} is invalid:{''.join(f'\n  {problem}' for problem in problems)}")


@dataclass(frozen=True)
class _Problem:
    location: str
    message: str

    @classmethod
    def from_details(cls, details: ErrorDetails, prefix: str | None) -> Self:
        parts = [prefix] if prefix else []
        return cls(".".join([*parts, *(str(part) for part in details["loc"])]), details["msg"])

    def __str__(self) -> str:
        return f"{self.location}: {self.message}" if self.location else self.message
