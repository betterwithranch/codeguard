from collections.abc import Hashable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Event, Lock


@dataclass
class PromptCacheWarmup:
    _lock: Lock = field(default_factory=Lock)
    _first_calls: dict[Hashable, Event] = field(default_factory=dict)

    @contextmanager
    def after_first_call(self, prefix: Hashable) -> Iterator[None]:
        with self._lock:
            earlier = self._first_calls.get(prefix)
            if earlier is None:
                self._first_calls[prefix] = Event()
        if earlier is not None:
            earlier.wait()
            yield
            return
        try:
            yield
        finally:
            self._first_calls[prefix].set()
