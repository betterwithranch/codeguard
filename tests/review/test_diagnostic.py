from codeguard.review import Severity


class TestDiagnostic:
    def test_id_ignores_message_severity_and_note(self, make_diagnostic):
        diagnostic = make_diagnostic()
        reworded = make_diagnostic(
            message="Reworded.", severity=Severity.WARNING, note="Call logger.info instead."
        )

        assert diagnostic.id == reworded.id

    def test_id_differs_by_line(self, make_diagnostic):
        diagnostic = make_diagnostic(line=2)
        moved = make_diagnostic(line=3)

        assert diagnostic.id != moved.id

    def test_str_indents_note_under_summary(self, make_diagnostic):
        diagnostic = make_diagnostic()

        assert str(diagnostic) == (
            f"a.py:1: error no-print: Use logging, not print. [{diagnostic.id}]\n"
            "  print bypasses log levels.\n"
            "  Call logger.info instead."
        )

    def test_str_without_note_is_summary_only(self, make_diagnostic):
        diagnostic = make_diagnostic(warning=True)

        assert str(diagnostic) == (
            f"a.py:1: warning no-breakpoint: Remove breakpoint(). [{diagnostic.id}]"
        )
