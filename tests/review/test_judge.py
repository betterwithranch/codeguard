import pytest
from pydantic import ValidationError

from codeguard.review import JudgeRequest, Severity, Verdict
from codeguard.review.judge import INSTRUCTIONS

THRESHOLD = 0.9


class TestJudgeRequest:
    def test_prompt_is_the_skill_text(self, make_skill):
        skill = make_skill()

        assert JudgeRequest(skill, "a.py").prompt == skill.text

    def test_instructions_end_with_the_numbered_file(self, make_skill):
        request = JudgeRequest(make_skill(), "a.py")

        assert request.instructions("x = 1\nprint(x)\n") == (
            f'{INSTRUCTIONS}\n<file path="a.py">\n     1\tx = 1\n     2\tprint(x)\n</file>\n'
        )

    def test_instructions_end_a_file_without_a_final_newline(self, make_skill):
        request = JudgeRequest(make_skill(), "a.py")

        assert request.instructions("x = 1") == (
            f'{INSTRUCTIONS}\n<file path="a.py">\n     1\tx = 1\n</file>\n'
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

        assert diagnostics == (make_diagnostic(judged=True, confidence=THRESHOLD),)

    def test_error_below_the_threshold_is_a_warning(
        self, make_violation, make_binding, make_diagnostic
    ):
        verdict = Verdict(violations=(make_violation(confidence=0.5),))

        diagnostics = verdict.diagnostics_for(make_binding(), "a.py", THRESHOLD)

        assert diagnostics == (
            make_diagnostic(judged=True, severity=Severity.WARNING, confidence=0.5),
        )

    def test_info_below_the_threshold_stays_info(
        self, make_violation, make_binding, make_diagnostic
    ):
        verdict = Verdict(violations=(make_violation(confidence=0.5),))

        diagnostics = verdict.diagnostics_for(
            make_binding(severity=Severity.INFO), "a.py", THRESHOLD
        )

        assert diagnostics == (
            make_diagnostic(judged=True, severity=Severity.INFO, confidence=0.5),
        )
