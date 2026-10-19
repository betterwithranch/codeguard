from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TextIO


@dataclass(frozen=True)
class PlannedCall:
    rule: str
    file: str
    cached: bool


@dataclass(frozen=True)
class JudgePlan:
    calls: tuple[PlannedCall, ...]

    def write(self, out: TextIO) -> None:
        uncached = [call for call in self.calls if not call.cached]
        out.write(
            f"Judge calls: {len(self.calls)} ({len(self.calls) - len(uncached)} cached, "
            f"{len(uncached)} to Claude)\n"
        )
        _write_counts(out, "By rule", (call.rule for call in uncached))
        _write_counts(out, "By file", (call.file for call in uncached))


def _write_counts(out: TextIO, heading: str, names: Iterable[str]) -> None:
    counts = Counter(names)
    if not counts:
        return
    out.write(f"\n{heading}, calls to Claude:\n")
    for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        out.write(f"  {count:>5}  {name}\n")
