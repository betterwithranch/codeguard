from pathlib import Path
from typing import Self

from pydantic import ValidationError
from pydantic_core import ErrorDetails


class ConfigError(Exception):
    @classmethod
    def invalid(cls, location: Path, error: ValidationError, prefix: str | None = None) -> Self:
        problems = "".join(_problem(problem, prefix) for problem in error.errors(include_url=False))
        return cls(f"{location} is invalid:{problems}")


def _problem(problem: ErrorDetails, prefix: str | None) -> str:
    parts = [prefix] if prefix else []
    location = ".".join([*parts, *(str(part) for part in problem["loc"])])
    return f"\n  {location}: {problem['msg']}" if location else f"\n  {problem['msg']}"
