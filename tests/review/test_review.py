from io import StringIO

from codeguard.review import Review


class TestReview:
    def test_error_diagnostic_blocks(self, make_diagnostic):
        result = Review(diagnostics=(make_diagnostic(warning=True), make_diagnostic(line=2)))

        assert result.blocks is True

    def test_warning_diagnostic_does_not_block(self, make_diagnostic):
        result = Review(diagnostics=(make_diagnostic(warning=True),))

        assert result.blocks is False

    def test_low_confidence_error_does_not_block(self, make_diagnostic):
        result = Review(diagnostics=(make_diagnostic(low_confidence=True),))

        assert result.blocks is False

    def test_write_lists_low_confidence_diagnostics_last(self, make_diagnostic):
        low = make_diagnostic(low_confidence=True, line=1)
        high = make_diagnostic(line=2)
        out = StringIO()

        Review(diagnostics=(low, high)).write(out)

        assert out.getvalue() == f"{high}\nLow confidence:\n{low}\n"
