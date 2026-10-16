from codeguard.review import JudgeRequest, Severity, Verdict


class TestJudgeRequest:
    def test_prompt_is_skill_text_then_file_path(self, make_skill):
        request = JudgeRequest(make_skill(), "a.py")

        assert request.prompt == (
            "# Responsibility placement\n\nA method lives on the type whose data it reads.\n\n"
            "a.py\n"
        )


class TestVerdict:
    def test_diagnostic_has_the_binding_skill_and_severity(
        self, make_violation, make_binding, make_diagnostic
    ):
        verdict = Verdict(violations=(make_violation(),))

        diagnostics = verdict.diagnostics_for(make_binding(severity=Severity.WARNING), "a.py")

        assert diagnostics == (make_diagnostic(judged=True, severity=Severity.WARNING),)

    def test_violations_in_other_files_are_left_out(self, make_violation, make_binding):
        verdict = Verdict(violations=(make_violation(file="b.py"),))

        assert verdict.diagnostics_for(make_binding(), "a.py") == ()
