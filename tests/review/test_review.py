from io import StringIO

from codeguard.review import Review


class TestReview:
    def test_error_diagnostic_blocks(self, make_diagnostic):
        result = Review(diagnostics=(make_diagnostic(warning=True), make_diagnostic(line=2)))

        assert result.blocks is True

    def test_warning_diagnostic_does_not_block(self, make_diagnostic):
        result = Review(diagnostics=(make_diagnostic(warning=True),))

        assert result.blocks is False

    def test_write_lists_each_diagnostic(self, make_diagnostic):
        warning = make_diagnostic(warning=True)
        error = make_diagnostic(line=2)
        out = StringIO()

        Review(diagnostics=(warning, error)).write(out)

        assert out.getvalue() == f"{warning}\n{error}\n"
