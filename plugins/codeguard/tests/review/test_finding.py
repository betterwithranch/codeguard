from codeguard.review import Severity


class TestFinding:
    def test_id_ignores_message_severity_and_note(self, make_finding):
        finding = make_finding()
        reworded = make_finding(
            message="Reworded.", severity=Severity.WARNING, note="Call logger.info instead."
        )

        assert finding.id == reworded.id

    def test_id_differs_by_line(self, make_finding):
        finding = make_finding(line=2)
        moved = make_finding(line=3)

        assert finding.id != moved.id

    def test_str_indents_note_under_summary(self, make_finding):
        finding = make_finding()

        assert str(finding) == (
            f"a.py:1: error no-print: Use logging, not print. [{finding.id}]\n"
            "  print bypasses log levels.\n"
            "  Call logger.info instead."
        )

    def test_str_without_note_is_summary_only(self, make_finding):
        finding = make_finding(warning=True)

        assert str(finding) == f"a.py:1: warning no-breakpoint: Remove breakpoint(). [{finding.id}]"
