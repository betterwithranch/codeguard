import pytest
from recording_judge import RecordingJudge
from spans import finished_span_attributes

from codeguard.review import CachedJudge, JudgeRequest, Verdict


def cached(repo, store, wrapped, **options) -> CachedJudge:
    return CachedJudge(wrapped=wrapped, store=store, root=repo.root, **options)


class TestCachedJudge:
    def test_uncached_request_goes_to_the_wrapped_judge(self, repo, store, make_skill):
        repo.write("a.py", "print(1)\n")
        wrapped = RecordingJudge()
        request = JudgeRequest(make_skill(), "a.py")

        cached(repo, store, wrapped).judge(request)

        assert wrapped.received == [request]

    def test_cached_verdict_is_returned_without_judging_again(
        self, repo, store, make_skill, make_violation
    ):
        repo.write("a.py", "print(1)\n")
        verdict = Verdict(violations=(make_violation(),))
        wrapped = RecordingJudge(verdict)
        judge = cached(repo, store, wrapped)
        request = JudgeRequest(make_skill(), "a.py")
        judge.judge(request)

        assert judge.judge(request) == verdict
        assert wrapped.received == [request]

    def test_cache_entry_that_is_not_a_verdict_is_an_error(self, repo, store, make_skill):
        repo.write("a.py", "print(1)\n")
        judge = cached(repo, store, RecordingJudge())
        request = JudgeRequest(make_skill(), "a.py")
        judge.judge(request)
        [key] = list(store)
        store[key] = "written by another version"

        with pytest.raises(TypeError, match=f"cache entry {key} is not a Verdict"):
            judge.judge(request)

    def test_has_a_request_only_after_judging_it(self, repo, store, make_skill):
        repo.write("a.py", "print(1)\n")
        judge = cached(repo, store, RecordingJudge())
        request = JudgeRequest(make_skill(), "a.py")
        before = judge.has(request)

        judge.judge(request)

        assert (before, judge.has(request)) == (False, True)

    def test_changed_file_is_judged_again(self, repo, store, make_skill):
        repo.write("a.py", "print(1)\n")
        wrapped = RecordingJudge()
        judge = cached(repo, store, wrapped)
        request = JudgeRequest(make_skill(), "a.py")
        judge.judge(request)
        repo.write("a.py", "print(2)\n")

        judge.judge(request)

        assert wrapped.received == [request, request]

    def test_changed_skill_text_is_judged_again(self, repo, store, make_skill):
        repo.write("a.py", "print(1)\n")
        wrapped = RecordingJudge()
        judge = cached(repo, store, wrapped)
        judge.judge(JudgeRequest(make_skill(), "a.py"))
        revised = JudgeRequest(make_skill(text="# Revised\n"), "a.py")

        judge.judge(revised)

        assert wrapped.received[-1] == revised

    def test_changed_wrapped_identity_is_judged_again(self, repo, store, make_skill):
        repo.write("a.py", "print(1)\n")
        request = JudgeRequest(make_skill(), "a.py")
        cached(repo, store, RecordingJudge(identity="first")).judge(request)
        second = RecordingJudge(identity="second")

        cached(repo, store, second).judge(request)

        assert second.received == [request]

    def test_each_lookup_records_whether_the_cache_had_the_verdict(
        self, repo, store, make_skill, make_violation, capfire
    ):
        repo.write("a.py", "print(1)\n")
        judge = cached(repo, store, RecordingJudge(Verdict(violations=(make_violation(),))))
        request = JudgeRequest(make_skill(), "a.py")

        judge.judge(request)
        judge.judge(request)

        lookup = {"rule": make_skill().name, "file": "a.py", "violations": 1}
        assert finished_span_attributes(capfire, "judge {rule} on {file}") == [
            {**lookup, "cache_hit": False},
            {**lookup, "cache_hit": True},
        ]

    def test_changed_version_is_judged_again(self, repo, store, make_skill):
        repo.write("a.py", "print(1)\n")
        request = JudgeRequest(make_skill(), "a.py")
        cached(repo, store, RecordingJudge()).judge(request)
        wrapped = RecordingJudge()

        cached(repo, store, wrapped, version="another version").judge(request)

        assert wrapped.received == [request]
