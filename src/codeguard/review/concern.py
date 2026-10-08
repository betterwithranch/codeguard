from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    name: str
    text: str


@dataclass(frozen=True)
class Concern:
    skill: Skill
    files: tuple[str, ...]
