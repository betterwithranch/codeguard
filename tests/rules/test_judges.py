from diskcache import Cache

from codeguard.claude_provider import ClaudeJudge
from codeguard.rules.judges import Judges


class TestJudges:
    def test_every_judge_shares_the_store_process_limit_and_warmup(self, tmp_path):
        judges = Judges(store=Cache(tmp_path))

        cached = judges.cached(tmp_path, "sonnet")
        uncached = judges.uncached(tmp_path, "opus")

        assert isinstance(cached.wrapped, ClaudeJudge)
        assert isinstance(uncached, ClaudeJudge)
        assert cached.store is judges.store
        assert cached.wrapped.processes is uncached.processes is judges.processes
        assert cached.wrapped.warmup is uncached.warmup is judges.warmup
