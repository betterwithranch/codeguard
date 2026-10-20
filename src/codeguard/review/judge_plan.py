from collections.abc import Callable
from dataclasses import dataclass
from typing import TextIO


@dataclass(frozen=True)
class PlannedCall:
    rule: str
    file: str
    cached: bool
    triggered: bool

    @property
    def status(self) -> str:
        if not self.triggered:
            return "skipped"
        return "cached" if self.cached else "claude"


@dataclass(frozen=True)
class JudgePlan:
    calls: tuple[PlannedCall, ...]

    def write(self, out: TextIO) -> None:
        made = [call for call in self.calls if call.triggered]
        cached = [call for call in made if call.cached]
        out.write(
            f"Judge calls: {len(made)} ({len(cached)} cached, {len(made) - len(cached)} to "
            f"Claude), {len(self.calls) - len(made)} skipped by triggers\n"
        )
        self._write_totals(out, "rule", lambda call: call.rule)
        self._write_totals(out, "file", lambda call: call.file)
        self._write_calls_by_file(out)

    def _write_totals(self, out: TextIO, heading: str, key: Callable[[PlannedCall], str]) -> None:
        if not self.calls:
            return
        totals: dict[str, dict[str, int]] = {}
        for call in self.calls:
            counts = totals.setdefault(key(call), {"claude": 0, "cached": 0, "skipped": 0})
            counts[call.status] += 1
        out.write(f"\nBy {heading}:\n  claude  cached  skipped  {heading}\n")
        for name, counts in sorted(
            totals.items(), key=lambda item: (-item[1]["claude"] - item[1]["cached"], item[0])
        ):
            out.write(
                f"  {counts['claude']:>6}  {counts['cached']:>6}  {counts['skipped']:>7}  {name}\n"
            )

    def _write_calls_by_file(self, out: TextIO) -> None:
        if not self.calls:
            return
        out.write("\nCalls by file:\n")
        for file in sorted({call.file for call in self.calls}):
            out.write(f"{file}\n")
            for call in sorted(
                (call for call in self.calls if call.file == file),
                key=lambda call: (call.status == "skipped", call.rule),
            ):
                out.write(f"  {call.status:<8} {call.rule}\n")
