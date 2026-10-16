from dataclasses import dataclass
from threading import Barrier

from recording_judge import RecordingJudge

from codeguard.review import JudgeCheck, JudgeRequest, Severity, Verdict

THRESHOLD = 0.9


@dataclass(frozen=True)
class WaitingJudge:
    barrier: Barrier
    identity: str = "waiting"

    def judge(self, request):
        self.barrier.wait()
        return Verdict(violations=())


class TestJudgeCheck:
    def test_every_file_is_judged_at_the_same_time(self, make_binding):
        files = [f"{index}.py" for index in range(40)]
        barrier = Barrier(len(files), timeout=5)

        JudgeCheck(make_binding(), WaitingJudge(barrier), THRESHOLD).check(files)

        assert not barrier.broken

    def test_no_matching_files_is_no_diagnostics(self, make_binding):
        check = JudgeCheck(make_binding(paths=("app/**",)), RecordingJudge(), THRESHOLD)

        assert check.check(["a.py"]) == []

    def test_each_file_is_its_own_request(self, make_binding, make_skill):
        judge = RecordingJudge()

        JudgeCheck(make_binding(), judge, THRESHOLD).check(["a.py", "b.py"])

        assert set(judge.received) == {
            JudgeRequest(make_skill(), "a.py"),
            JudgeRequest(make_skill(), "b.py"),
        }

    def test_file_outside_the_binding_paths_is_not_judged(self, make_binding):
        judge = RecordingJudge()

        JudgeCheck(make_binding(paths=("app/**",)), judge, THRESHOLD).check(["a.py"])

        assert judge.received == []

    def test_diagnostics_have_the_binding_severity(
        self, make_binding, make_violation, make_diagnostic
    ):
        judge = RecordingJudge(Verdict(violations=(make_violation(),)))
        check = JudgeCheck(make_binding(severity=Severity.WARNING), judge, THRESHOLD)

        assert check.check(["a.py"]) == [make_diagnostic(judged=True, severity=Severity.WARNING)]

    def test_error_below_the_threshold_is_a_warning(
        self, make_binding, make_violation, make_diagnostic
    ):
        judge = RecordingJudge(Verdict(violations=(make_violation(confidence=0.5),)))
        check = JudgeCheck(make_binding(), judge, THRESHOLD)

        assert check.check(["a.py"]) == [make_diagnostic(judged=True, severity=Severity.WARNING)]
