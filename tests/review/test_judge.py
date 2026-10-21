import pytest
from pydantic import ValidationError

from codeguard.review import JudgeRequest, Severity, Verdict
from codeguard.review.judge import INSTRUCTIONS, Violation

THRESHOLD = 0.9


class TestJudgeRequest:
    def test_prompt_is_the_skill_text(self, make_skill, make_judge_request):
        skill = make_skill()

        assert make_judge_request(skill=skill).prompt == skill.text

    def test_changed_lines_are_numbered_with_their_file_line_numbers(self, tmp_path, make_skill):
        (tmp_path / "pricing.py").write_text(
            "DISCOUNT = 5\n\n\ndef discounted(total):\n    return total - DISCOUNT\n"
        )

        request = JudgeRequest.of_change(make_skill(), tmp_path, "pricing.py", frozenset({4, 5}))

        assert request == JudgeRequest(
            make_skill(),
            "pricing.py",
            "     4\tdef discounted(total):\n     5\t    return total - DISCOUNT\n",
        )

    def test_no_changed_lines_is_the_whole_file(self, tmp_path, make_skill):
        (tmp_path / "pricing.py").write_text("DISCOUNT = 5\nTAX = 2")

        request = JudgeRequest.of_change(make_skill(), tmp_path, "pricing.py", None)

        assert request == JudgeRequest(
            make_skill(), "pricing.py", "     1\tDISCOUNT = 5\n     2\tTAX = 2\n"
        )

    def test_changed_point_past_the_end_of_the_file_is_left_out(self, tmp_path, make_skill):
        (tmp_path / "pricing.py").write_text("DISCOUNT = 5\n")

        request = JudgeRequest.of_change(make_skill(), tmp_path, "pricing.py", frozenset({1, 2}))

        assert request == JudgeRequest(make_skill(), "pricing.py", "     1\tDISCOUNT = 5\n")

    def test_lines_are_numbered_as_git_numbers_them(self, tmp_path, make_skill):
        (tmp_path / "pricing.py").write_text("DISCOUNT = 5\f\nTAX = 2\n")

        request = JudgeRequest.of_change(make_skill(), tmp_path, "pricing.py", frozenset({2}))

        assert request == JudgeRequest(make_skill(), "pricing.py", "     2\tTAX = 2\n")

    def test_instructions_end_with_the_changes(self, make_judge_request):
        request = make_judge_request(file="pricing.py", changes="     4\tdef discounted(total):\n")

        assert request.instructions == (
            f'{INSTRUCTIONS}\n<changes path="pricing.py">\n     4\tdef discounted(total):\n'
            "</changes>\n"
        )


class TestViolation:
    def test_confidence_above_one_is_invalid(self, make_violation):
        with pytest.raises(ValidationError):
            make_violation(confidence=1.1)

    def test_note_is_invalid(self):
        with pytest.raises(ValidationError):
            Violation.model_validate(
                {
                    "file": "a.py",
                    "line": 1,
                    "message": "Move it.",
                    "note": "Fix it.",
                    "confidence": 1,
                }
            )


class TestVerdict:
    def test_unconfident_violation_shows_why_it_is_only_a_warning(
        self, make_violation, make_binding
    ):
        verdict = Verdict(violations=(make_violation(confidence=0.7),))

        [diagnostic] = verdict.diagnostics_for(make_binding(), "a.py", THRESHOLD)

        assert str(diagnostic).startswith(
            f"a.py:1: warning {make_binding().rule}: Use logging, not print. (confidence 0.70)"
        )

    def test_judged_diagnostic_prints_only_its_summary(self, make_violation, make_binding):
        verdict = Verdict(violations=(make_violation(),))

        [diagnostic] = verdict.diagnostics_for(make_binding(), "a.py", THRESHOLD)

        assert str(diagnostic) == (
            f"a.py:1: error {make_binding().rule}: Use logging, not print. (confidence 1.00) "
            f"[{diagnostic.id}]"
        )

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
