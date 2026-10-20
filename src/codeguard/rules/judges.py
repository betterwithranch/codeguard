import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import Semaphore

from diskcache import Cache

from codeguard.claude_provider import ClaudeJudge, Deadline, PromptCacheWarmup
from codeguard.review import CachedJudge, Judge

_JUDGEMENT_CACHE_DIR = Path.home() / ".cache" / "codeguard" / "judgements"


@dataclass(frozen=True)
class Judges:
    store: Cache = field(default_factory=lambda: Cache(_JUDGEMENT_CACHE_DIR))
    processes: Semaphore = field(default_factory=lambda: Semaphore(os.process_cpu_count() or 1))
    warmup: PromptCacheWarmup = field(default_factory=PromptCacheWarmup)

    def cached(self, root: Path, model: str, deadline: Deadline | None = None) -> CachedJudge:
        return CachedJudge(self.uncached(root, model, deadline), self.store, root)

    def uncached(self, root: Path, model: str, deadline: Deadline | None = None) -> Judge:
        return ClaudeJudge(root, model, self.processes, warmup=self.warmup, deadline=deadline)
