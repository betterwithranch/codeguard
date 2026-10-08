from io import StringIO

from codeguard.review import Review


class TestReview:
    def test_error_finding_blocks(self, make_finding):
        result = Review(findings=(make_finding(warning=True), make_finding(line=2)))

        assert result.blocks is True

    def test_warning_finding_does_not_block(self, make_finding):
        result = Review(findings=(make_finding(warning=True),))

        assert result.blocks is False

    def test_low_confidence_error_does_not_block(self, make_finding):
        result = Review(findings=(make_finding(low_confidence=True),))

        assert result.blocks is False

    def test_write_lists_low_confidence_findings_last(self, make_finding):
        low = make_finding(low_confidence=True, line=1)
        high = make_finding(line=2)
        out = StringIO()

        Review(findings=(low, high)).write(out)

        assert out.getvalue() == f"{high}\nLow confidence:\n{low}\n"
