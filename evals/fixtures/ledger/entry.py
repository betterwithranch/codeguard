from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    amount: int
