import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

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
        key = self._key(request)
        if key not in self.store:
            self.store[key] = self.wrapped.judge(request)
        return self.store[key]

    def _key(self, request: JudgeRequest) -> str:
        text = (self.root / request.file).read_text()
        parts = (self.version, self.identity, request.skill.text, request.file, _digest(text))
        return _digest("\0".join(parts))


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
