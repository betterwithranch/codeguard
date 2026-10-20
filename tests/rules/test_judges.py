from diskcache import Cache

from codeguard.claude_provider import ClaudeJudge
from codeguard.config import JudgeConfig, JudgeProvider
from codeguard.gemini_provider import GeminiJudge
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

    def test_gemini_config_builds_gemini_judges_with_its_model(self, tmp_path):
        config = JudgeConfig(provider=JudgeProvider.GEMINI, model="gemini-3.1-pro-preview")
        judges = Judges(config, store=Cache(tmp_path))

        judge = judges.uncached(tmp_path, "claude-sonnet-5-5")

        assert isinstance(judge, GeminiJudge)
        assert judge.model == "gemini-3.1-pro-preview"
        assert judge.processes is judges.processes
