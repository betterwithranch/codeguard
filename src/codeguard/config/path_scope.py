from dataclasses import dataclass
from pathlib import PurePath


@dataclass(frozen=True)
class PathScope:
    paths: tuple[str, ...] = ("**",)
    exclude_paths: tuple[str, ...] = ()

    def matches(self, file: str) -> bool:
        return _matches_any(file, self.paths) and not _matches_any(file, self.exclude_paths)


def _matches_any(file: str, patterns: tuple[str, ...]) -> bool:
    return any(PurePath(file).full_match(pattern) for pattern in patterns)
