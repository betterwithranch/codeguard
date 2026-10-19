import io

from codeguard.review import JudgePlan, PlannedCall


class TestJudgePlan:
    def test_counts_calls_to_claude_by_rule_and_by_file(self):
        plan = JudgePlan(
            calls=(
                PlannedCall(rule="no-dead-code", file="a.py", cached=False),
                PlannedCall(rule="no-dead-code", file="b.py", cached=False),
                PlannedCall(rule="enum-usage", file="a.py", cached=False),
                PlannedCall(rule="enum-usage", file="b.py", cached=True),
            )
        )
        out = io.StringIO()

        plan.write(out)

        assert out.getvalue() == (
            "Judge calls: 4 (1 cached, 3 to Claude)\n"
            "\n"
            "By rule, calls to Claude:\n"
            "      2  no-dead-code\n"
            "      1  enum-usage\n"
            "\n"
            "By file, calls to Claude:\n"
            "      2  a.py\n"
            "      1  b.py\n"
        )

    def test_plan_without_calls_reports_only_the_total(self):
        out = io.StringIO()

        JudgePlan(calls=()).write(out)

        assert out.getvalue() == "Judge calls: 0 (0 cached, 0 to Claude)\n"
