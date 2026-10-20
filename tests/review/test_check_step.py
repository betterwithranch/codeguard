from dataclasses import dataclass, field
from threading import Barrier

from codeguard.review import CheckStep, Diagnostic


@dataclass(frozen=True)
class RecordingCheck:
    found: list[Diagnostic] = field(default_factory=list)
    received: list[list[str]] = field(default_factory=list)

    def check(self, files):
        self.received.append(list(files))
        return self.found


@dataclass(frozen=True)
class WaitingCheck:
    barrier: Barrier

    def check(self, files):
        self.barrier.wait()
        return []


class TestCheckStep:
    def test_checks_run_at_the_same_time(self):
        barrier = Barrier(2, timeout=5)

        CheckStep(checks=(WaitingCheck(barrier), WaitingCheck(barrier))).run(["a.py"], ())

        assert not barrier.broken

    def test_step_without_checks_keeps_earlier_diagnostics(self, make_diagnostic):
        assert CheckStep(checks=()).run(["a.py"], (make_diagnostic(),)) == (make_diagnostic(),)

    def test_file_with_blocking_diagnostic_is_not_checked(self, make_diagnostic):
        check = RecordingCheck()

        CheckStep(checks=(check,)).run(["a.py", "b.py"], (make_diagnostic(),))

        assert check.received == [["b.py"]]

    def test_file_with_only_a_warning_is_checked(self, make_diagnostic):
        check = RecordingCheck()

        CheckStep(checks=(check,)).run(["a.py"], (make_diagnostic(warning=True),))

        assert check.received == [["a.py"]]

    def test_diagnostics_follow_earlier_diagnostics(self, make_diagnostic):
        warning = make_diagnostic(warning=True)
        found = make_diagnostic(file="b.py")

        diagnostics = CheckStep(checks=(RecordingCheck(found=[found]),)).run(["a.py"], (warning,))

        assert diagnostics == (warning, found)
