from collections.abc import Sequence
from dataclasses import dataclass

from codeguard.config.binding import Binding
from codeguard.review import Concern


@dataclass(frozen=True)
class Config:
    bindings: tuple[Binding, ...]

    def concerns(self, files: Sequence[str]) -> list[Concern]:
        return [concern for binding in self.bindings if (concern := binding.concern(files))]
