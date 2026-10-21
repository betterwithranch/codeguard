import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import logfire
from diskcache import Cache

from codeguard.review.judge import INSTRUCTIONS, Judge, Judgement, JudgeRequest, Verdict

_CACHE_VERSION = "\0".join((INSTRUCTIONS, json.dumps(Verdict.model_json_schema())))


@dataclass(frozen=True)
class _StoredJudgement:
    verdict: Verdict
    read_digests: Mapping[str, str | None]


@dataclass(frozen=True)
class CachedJudge:
    wrapped: Judge
    store: Cache
    root: Path
    version: str = _CACHE_VERSION

    @property
    def identity(self) -> str:
        return self.wrapped.identity

    def judge(self, request: JudgeRequest) -> Judgement:
        with logfire.span(
            "judge {rule} on {file}", rule=request.skill.name, file=request.file
        ) as span:
            key = self._key(request)
            stored = self._stored(key)
            span.set_attribute("cache_hit", stored is not None)
            if stored is None:
                judgement = self.wrapped.judge(request)
                stored = _StoredJudgement(
                    judgement.verdict,
                    {file: self._digest_of(file) for file in judgement.read_files},
                )
                self.store[key] = stored
            span.set_attribute("violations", len(stored.verdict.violations))
            return Judgement(stored.verdict, tuple(stored.read_digests))

    def has(self, request: JudgeRequest) -> bool:
        return self._stored(self._key(request)) is not None

    def _stored(self, key: str) -> _StoredJudgement | None:
        if key not in self.store:
            return None
        stored = self.store[key]
        if not isinstance(stored, _StoredJudgement):
            raise TypeError(f"cache entry {key} is not a stored judgement")
        unchanged = all(
            digest is not None and self._digest_of(file) == digest
            for file, digest in stored.read_digests.items()
        )
        return stored if unchanged else None

    def _digest_of(self, file: str) -> str | None:
        root = self.root.resolve()
        path = (root / file).resolve()
        if not path.is_relative_to(root):
            return None
        return _digest(path.read_bytes()) if path.is_file() else "missing"

    def _key(self, request: JudgeRequest) -> str:
        parts = (
            self.version,
            self.identity,
            request.skill.text,
            request.file,
            _digest(request.changes.encode()),
            self._digest_of(request.file) or "",
        )
        return _digest("\0".join(parts).encode())


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
