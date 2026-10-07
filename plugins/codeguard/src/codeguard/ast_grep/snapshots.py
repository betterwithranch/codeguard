from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

import yaml

SNAPSHOT_DIR = "__snapshots__"


@dataclass(frozen=True)
class SnapshotFile:
    rule: str
    path: Path
    cases: frozenset[str]

    @classmethod
    def load(cls, path: Path) -> Self:
        snapshot = _read(path)
        return cls(rule=snapshot["id"], path=path, cases=frozenset(snapshot["snapshots"]))

    def stale_problem(self, root: Path) -> str:
        return (
            f"{self.path.relative_to(root)}: stale snapshot entries for {self.rule}. "
            "Run codeguard test --update-all."
        )


@dataclass(frozen=True)
class Snapshots:
    invalid_cases: dict[str, frozenset[str]]
    snapshots: tuple[SnapshotFile, ...]

    @classmethod
    def load(cls, test_dir: Path) -> Self:
        snapshot_dir = test_dir / SNAPSHOT_DIR
        paths = sorted(test_dir.rglob("*.y*ml"))
        tests = [_read(path) for path in paths if snapshot_dir not in path.parents]
        return cls(
            invalid_cases={test["id"]: frozenset(test.get("invalid", [])) for test in tests},
            snapshots=tuple(
                SnapshotFile.load(path) for path in paths if snapshot_dir in path.parents
            ),
        )

    def stale(self) -> list[SnapshotFile]:
        return [
            snapshot
            for snapshot in self.snapshots
            if not snapshot.cases <= self.invalid_cases.get(snapshot.rule, frozenset())
        ]


def _read(path: Path) -> Any:
    return yaml.safe_load(path.read_text())
