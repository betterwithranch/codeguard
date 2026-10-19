import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import logfire
from diskcache import Cache

from codeguard.review.judge import INSTRUCTIONS, Judge, JudgeRequest, Verdict

_CACHE_VERSION = "\0".join((INSTRUCTIONS, json.dumps(Verdict.model_json_schema())))


@dataclass(frozen=True)
class CachedJudge:
    wrapped: Judge
    store: Cache
    root: Path
    version: str = _CACHE_VERSION

    @property
    def identity(self) -> str:
        return self.wrapped.identity

    def judge(self, request: JudgeRequest) -> Verdict:
        with logfire.span(
            "judge {rule} on {file}", rule=request.skill.name, file=request.file
        ) as span:
            key = self._key(request)
            cache_hit = key in self.store
            span.set_attribute("cache_hit", cache_hit)
            if not cache_hit:
                self.store[key] = self.wrapped.judge(request)
            verdict = self.store[key]
            if not isinstance(verdict, Verdict):
                raise TypeError(f"cache entry {key} is not a Verdict")
            span.set_attribute("violations", len(verdict.violations))
            return verdict

    def _key(self, request: JudgeRequest) -> str:
        text = (self.root / request.file).read_text()
        parts = (self.version, self.identity, request.skill.text, request.file, _digest(text))
        return _digest("\0".join(parts))


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
