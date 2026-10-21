import os
from dataclasses import dataclass, field
from pathlib import Path
from threading import Semaphore

from diskcache import Cache

from codeguard.claude_provider import ClaudeJudge, PromptCacheWarmup
from codeguard.config import JudgeConfig, JudgeProvider
from codeguard.gemini_provider import DeferredGeminiClient, GeminiJudge
from codeguard.review import CachedJudge, Deadline, Judge

_JUDGEMENT_CACHE_DIR = Path.home() / ".cache" / "codeguard" / "judgements"


@dataclass(frozen=True)
class Judges:
    config: JudgeConfig = JudgeConfig()
    store: Cache = field(default_factory=lambda: Cache(_JUDGEMENT_CACHE_DIR))
    processes: Semaphore = field(default_factory=lambda: Semaphore(os.process_cpu_count() or 1))
    warmup: PromptCacheWarmup = field(default_factory=PromptCacheWarmup)

    def cached(self, root: Path, model: str, deadline: Deadline | None = None) -> CachedJudge:
        return CachedJudge(self.uncached(root, model, deadline), self.store)

    def uncached(self, root: Path, model: str, deadline: Deadline | None = None) -> Judge:
        model = self.config.model_for(model)
        if self.config.provider is JudgeProvider.GEMINI:
            client = DeferredGeminiClient(self.config.project, self.config.location)
            return GeminiJudge(root, model, client, self.processes, deadline=deadline)
        return ClaudeJudge(root, model, self.processes, warmup=self.warmup, deadline=deadline)
