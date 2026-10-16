from recording_judge import RecordingJudge

from codeguard.review import JudgeCheck, JudgeRequest, Severity, Verdict


class TestJudgeCheck:
    def test_each_file_is_its_own_request(self, make_binding, make_skill):
        judge = RecordingJudge()

        JudgeCheck(make_binding(), judge).check(["a.py", "b.py"])

        assert set(judge.received) == {
            JudgeRequest(make_skill(), "a.py"),
            JudgeRequest(make_skill(), "b.py"),
        }

    def test_file_outside_the_binding_paths_is_not_judged(self, make_binding):
        judge = RecordingJudge()

        JudgeCheck(make_binding(paths=("app/**",)), judge).check(["a.py"])

        assert judge.received == []

    def test_diagnostics_have_the_binding_severity(
        self, make_binding, make_violation, make_diagnostic
    ):
        judge = RecordingJudge(Verdict(violations=(make_violation(),)))

        diagnostics = JudgeCheck(make_binding(severity=Severity.WARNING), judge).check(["a.py"])

        assert diagnostics == [make_diagnostic(judged=True, severity=Severity.WARNING)]
