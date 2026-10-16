import pytest
from pydantic import ValidationError

from codeguard.review import JudgeRequest, Severity, Verdict

THRESHOLD = 0.9


class TestJudgeRequest:
    def test_prompt_is_skill_text_then_file_path(self, make_skill):
        request = JudgeRequest(make_skill(), "a.py")

        assert request.prompt == (
            "# Responsibility placement\n\nA method lives on the type whose data it reads.\n\n"
            "a.py\n"
        )


class TestViolation:
    def test_confidence_above_one_is_invalid(self, make_violation):
        with pytest.raises(ValidationError):
            make_violation(confidence=1.1)


class TestVerdict:
    def test_diagnostic_has_the_binding_skill_and_severity(
        self, make_violation, make_binding, make_diagnostic
    ):
        verdict = Verdict(violations=(make_violation(),))

        diagnostics = verdict.diagnostics_for(
            make_binding(severity=Severity.WARNING), "a.py", THRESHOLD
        )

        assert diagnostics == (make_diagnostic(judged=True, severity=Severity.WARNING),)

    def test_violations_in_other_files_are_left_out(self, make_violation, make_binding):
        verdict = Verdict(violations=(make_violation(file="b.py"),))

        assert verdict.diagnostics_for(make_binding(), "a.py", THRESHOLD) == ()

    def test_error_at_the_threshold_stays_an_error(
        self, make_violation, make_binding, make_diagnostic
    ):
        verdict = Verdict(violations=(make_violation(confidence=THRESHOLD),))

        diagnostics = verdict.diagnostics_for(make_binding(), "a.py", THRESHOLD)

        assert diagnostics == (make_diagnostic(judged=True),)

    def test_error_below_the_threshold_is_a_warning(
        self, make_violation, make_binding, make_diagnostic
    ):
        verdict = Verdict(violations=(make_violation(confidence=0.5),))

        diagnostics = verdict.diagnostics_for(make_binding(), "a.py", THRESHOLD)

        assert diagnostics == (make_diagnostic(judged=True, severity=Severity.WARNING),)

    def test_info_below_the_threshold_stays_info(
        self, make_violation, make_binding, make_diagnostic
    ):
        verdict = Verdict(violations=(make_violation(confidence=0.5),))

        diagnostics = verdict.diagnostics_for(
            make_binding(severity=Severity.INFO), "a.py", THRESHOLD
        )

        assert diagnostics == (make_diagnostic(judged=True, severity=Severity.INFO),)
