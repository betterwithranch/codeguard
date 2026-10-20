from dataclasses import dataclass
from threading import Barrier

from recording_judge import RecordingJudge

from codeguard.config import ChangeKind
from codeguard.review import (
    Diagnostic,
    JudgeCheck,
    JudgeError,
    JudgeRequest,
    Severity,
    Verdict,
)
from codeguard.working_tree import AllLines, ChangedLines

THRESHOLD = 0.9


@dataclass(frozen=True)
class WaitingJudge:
    barrier: Barrier
    identity: str = "waiting"

    def judge(self, request):
        self.barrier.wait()
        return Verdict(violations=())


@dataclass(frozen=True)
class FailingJudge:
    identity: str = "failing"

    def judge(self, request):
        raise JudgeError("claude exited with 1.")


class TestJudgeCheck:
    def test_failed_judge_call_is_an_error_on_the_file(self, make_binding, make_skill):
        check = JudgeCheck(make_binding(), FailingJudge(), THRESHOLD, AllLines(()))

        assert check.check(["a.py"]) == [
            Diagnostic(
                rule=make_skill().name,
                file="a.py",
                line=None,
                message="The judge call failed, so this rule was not checked.",
                severity=Severity.ERROR,
                note="claude exited with 1.",
            )
        ]

    def test_failed_judge_call_has_the_binding_severity(self, make_binding, make_skill):
        check = JudgeCheck(
            make_binding(severity=Severity.WARNING), FailingJudge(), THRESHOLD, AllLines(())
        )

        assert check.check(["a.py"]) == [
            Diagnostic(
                rule=make_skill().name,
                file="a.py",
                line=None,
                message="The judge call failed, so this rule was not checked.",
                severity=Severity.WARNING,
                note="claude exited with 1.",
            )
        ]

    def test_every_file_is_judged_at_the_same_time(self, make_binding):
        files = [f"{index}.py" for index in range(40)]
        barrier = Barrier(len(files), timeout=5)

        JudgeCheck(make_binding(), WaitingJudge(barrier), THRESHOLD, AllLines(())).check(files)

        assert not barrier.broken

    def test_no_matching_files_is_no_diagnostics(self, make_binding):
        check = JudgeCheck(
            make_binding(paths=("app/**",)), RecordingJudge(), THRESHOLD, AllLines(())
        )

        assert check.check(["a.py"]) == []

    def test_each_file_is_its_own_request(self, make_binding, make_skill):
        judge = RecordingJudge()

        JudgeCheck(make_binding(), judge, THRESHOLD, AllLines(())).check(["a.py", "b.py"])

        assert set(judge.received) == {
            JudgeRequest(make_skill(), "a.py"),
            JudgeRequest(make_skill(), "b.py"),
        }

    def test_file_outside_the_binding_paths_is_not_judged(self, make_binding):
        judge = RecordingJudge()

        JudgeCheck(make_binding(paths=("app/**",)), judge, THRESHOLD, AllLines(())).check(["a.py"])

        assert judge.received == []

    def test_file_whose_changes_miss_the_triggers_is_not_judged(self, make_binding):
        judge = RecordingJudge()
        scope = ChangedLines({"a.py": frozenset({1})}).with_kinds(
            {"a.py": frozenset({ChangeKind.COMMENT, ChangeKind.ANY})}
        )
        binding = make_binding(triggers=frozenset({ChangeKind.CLASS_HEADER}))

        JudgeCheck(binding, judge, THRESHOLD, scope).check(["a.py"])

        assert judge.received == []

    def test_file_whose_changes_touch_a_trigger_is_judged(self, make_binding, make_skill):
        judge = RecordingJudge()
        scope = ChangedLines({"a.py": frozenset({1})}).with_kinds(
            {"a.py": frozenset({ChangeKind.COMMENT, ChangeKind.ANY})}
        )
        binding = make_binding(triggers=frozenset({ChangeKind.COMMENT, ChangeKind.CLASS_HEADER}))

        JudgeCheck(binding, judge, THRESHOLD, scope).check(["a.py"])

        assert judge.received == [JudgeRequest(make_skill(), "a.py")]

    def test_file_without_change_kinds_is_judged(self, make_binding, make_skill):
        judge = RecordingJudge()
        binding = make_binding(triggers=frozenset({ChangeKind.CLASS_HEADER}))

        JudgeCheck(binding, judge, THRESHOLD, ChangedLines({"a.md": frozenset({1})})).check(
            ["a.md"]
        )

        assert judge.received == [JudgeRequest(make_skill(), "a.md")]

    def test_binding_without_triggers_judges_every_changed_file(self, make_binding, make_skill):
        judge = RecordingJudge()
        scope = ChangedLines({"a.py": frozenset({1})}).with_kinds(
            {"a.py": frozenset({ChangeKind.COMMENT, ChangeKind.ANY})}
        )

        JudgeCheck(make_binding(), judge, THRESHOLD, scope).check(["a.py"])

        assert judge.received == [JudgeRequest(make_skill(), "a.py")]

    def test_diagnostics_have_the_binding_severity(
        self, make_binding, make_violation, make_diagnostic
    ):
        judge = RecordingJudge(Verdict(violations=(make_violation(),)))
        check = JudgeCheck(make_binding(severity=Severity.WARNING), judge, THRESHOLD, AllLines(()))

        assert check.check(["a.py"]) == [make_diagnostic(judged=True, severity=Severity.WARNING)]

    def test_error_below_the_threshold_is_a_warning(
        self, make_binding, make_violation, make_diagnostic
    ):
        judge = RecordingJudge(Verdict(violations=(make_violation(confidence=0.5),)))
        check = JudgeCheck(make_binding(), judge, THRESHOLD, AllLines(()))

        assert check.check(["a.py"]) == [make_diagnostic(judged=True, severity=Severity.WARNING)]
