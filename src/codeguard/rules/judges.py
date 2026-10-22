from dataclasses import dataclass, field
from pathlib import Path
from threading import Semaphore

from diskcache import Cache

from codeguard.claude_provider import ClaudeJudge, PromptCacheWarmup
from codeguard.config import JudgeConfig, JudgeModel, JudgeProvider
from codeguard.gemini_provider import DeferredGeminiClient, GeminiJudge
from codeguard.review import CachedJudge, Deadline, Judge

_JUDGEMENT_CACHE_DIR = Path.home() / ".cache" / "codeguard" / "judgements"


@dataclass(frozen=True)
class Judges:
    config: JudgeConfig = JudgeConfig()
    store: Cache = field(default_factory=lambda: Cache(_JUDGEMENT_CACHE_DIR))
    warmup: PromptCacheWarmup = field(default_factory=PromptCacheWarmup)
    processes: dict[JudgeProvider, Semaphore] = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "processes",
            {provider: Semaphore(self.config.concurrency(provider)) for provider in JudgeProvider},
        )

    def cached(
        self, root: Path, model: JudgeModel, deadline: Deadline | None = None
    ) -> CachedJudge:
        return CachedJudge(self.uncached(root, model, deadline), self.store, root)

    def uncached(self, root: Path, model: JudgeModel, deadline: Deadline | None = None) -> Judge:
        processes = self.processes[model.provider]
        if model.provider is JudgeProvider.GEMINI:
            client = DeferredGeminiClient(self.config.project, self.config.location)
            return GeminiJudge(root, model.name, client, processes, deadline=deadline)
        return ClaudeJudge(root, model.name, processes, warmup=self.warmup, deadline=deadline)
