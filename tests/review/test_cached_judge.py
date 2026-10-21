import pytest
from recording_judge import RecordingJudge
from spans import finished_span_attributes

from codeguard.review import CachedJudge, Verdict


class TestCachedJudge:
    def test_uncached_request_goes_to_the_wrapped_judge(self, store, make_judge_request):
        wrapped = RecordingJudge()
        request = make_judge_request()

        CachedJudge(wrapped, store).judge(request)

        assert wrapped.received == [request]

    def test_cached_verdict_is_returned_without_judging_again(
        self, store, make_judge_request, make_violation
    ):
        verdict = Verdict(violations=(make_violation(),))
        wrapped = RecordingJudge(verdict)
        judge = CachedJudge(wrapped, store)
        request = make_judge_request()
        judge.judge(request)

        assert judge.judge(request) == verdict
        assert wrapped.received == [request]

    def test_cache_entry_that_is_not_a_verdict_is_an_error(self, store, make_judge_request):
        judge = CachedJudge(RecordingJudge(), store)
        request = make_judge_request()
        judge.judge(request)
        [key] = list(store)
        store[key] = "written by another version"

        with pytest.raises(TypeError, match=f"cache entry {key} is not a Verdict"):
            judge.judge(request)

    def test_has_a_request_only_after_judging_it(self, store, make_judge_request):
        judge = CachedJudge(RecordingJudge(), store)
        request = make_judge_request()
        before = judge.has(request)

        judge.judge(request)

        assert (before, judge.has(request)) == (False, True)

    def test_changed_content_is_judged_again(self, store, make_judge_request):
        wrapped = RecordingJudge()
        judge = CachedJudge(wrapped, store)
        judge.judge(make_judge_request())
        changed = make_judge_request(content="print(2)\n")

        judge.judge(changed)

        assert wrapped.received[-1] == changed

    def test_changed_skill_text_is_judged_again(self, store, make_skill, make_judge_request):
        wrapped = RecordingJudge()
        judge = CachedJudge(wrapped, store)
        judge.judge(make_judge_request())
        revised = make_judge_request(skill=make_skill(text="# Revised\n"))

        judge.judge(revised)

        assert wrapped.received[-1] == revised

    def test_changed_wrapped_identity_is_judged_again(self, store, make_judge_request):
        request = make_judge_request()
        CachedJudge(RecordingJudge(identity="first"), store).judge(request)
        second = RecordingJudge(identity="second")

        CachedJudge(second, store).judge(request)

        assert second.received == [request]

    def test_each_lookup_records_whether_the_cache_had_the_verdict(
        self, store, make_violation, capfire, make_judge_request
    ):
        judge = CachedJudge(RecordingJudge(Verdict(violations=(make_violation(),))), store)
        request = make_judge_request()

        judge.judge(request)
        judge.judge(request)

        lookup = {"rule": request.skill.name, "file": "a.py", "violations": 1}
        assert finished_span_attributes(capfire, "judge {rule} on {file}") == [
            {**lookup, "cache_hit": False},
            {**lookup, "cache_hit": True},
        ]

    def test_changed_version_is_judged_again(self, store, make_judge_request):
        request = make_judge_request()
        CachedJudge(RecordingJudge(), store).judge(request)
        wrapped = RecordingJudge()

        CachedJudge(wrapped, store, version="another version").judge(request)

        assert wrapped.received == [request]
