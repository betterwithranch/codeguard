from recording_judge import RecordingJudge

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

    def test_changed_version_is_judged_again(self, repo, store, make_skill):
        repo.write("a.py", "print(1)\n")
        request = JudgeRequest(make_skill(), "a.py")
        cached(repo, store, RecordingJudge()).judge(request)
        wrapped = RecordingJudge()

        cached(repo, store, wrapped, version="another version").judge(request)

        assert wrapped.received == [request]
