from enum import StrEnum
from functools import cache
from pathlib import Path, PurePath
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict

_LANGUAGES_DIR = Path(__file__).parent / "languages"

type AstGrepRule = dict[str, object]


class NodeKind(StrEnum):
    COMMENT = "comments"
    IMPORT = "imports"
    NAME = "names"
    DEFINITION = "definitions"


class Syntax(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    language: str
    extensions: tuple[str, ...]
    comments: AstGrepRule
    imports: AstGrepRule
    names: AstGrepRule
    definitions: AstGrepRule

    @classmethod
    def for_file(cls, file: str) -> Self | None:
        extension = PurePath(file).suffix.removeprefix(".")
        return next((syntax for syntax in cls.supported() if extension in syntax.extensions), None)

    @classmethod
    @cache
    def supported(cls) -> tuple[Self, ...]:
        return tuple(
            cls.model_validate(yaml.safe_load(file.read_text()))
            for file in sorted(_LANGUAGES_DIR.glob("*.yml"))
        )

    @property
    def inline_rules(self) -> str:
        return "---\n".join(
            yaml.safe_dump(
                {"id": str(kind), "language": self.language, "rule": getattr(self, kind)}
            )
            for kind in NodeKind
        )
