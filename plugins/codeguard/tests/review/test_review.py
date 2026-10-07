from codeguard.review import Review


class TestReview:
    def test_error_finding_blocks(self, make_finding):
        result = Review(findings=(make_finding(warning=True), make_finding(line=2)))

        assert result.blocks is True

    def test_warning_finding_does_not_block(self, make_finding):
        result = Review(findings=(make_finding(warning=True),))

        assert result.blocks is False
