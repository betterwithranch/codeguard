from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self


@dataclass(frozen=True)
class StopEvent:
    cwd: Path
    permission_mode: str

    @classmethod
    def from_hook_input(cls, payload: dict[str, Any]) -> Self:
        return cls(cwd=Path(payload["cwd"]), permission_mode=payload["permission_mode"])
