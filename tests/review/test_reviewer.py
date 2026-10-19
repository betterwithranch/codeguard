from recording_judge import RecordingJudge

from codeguard.config import Ruleset
from codeguard.pattern_rules import PatternRuleCheck
from codeguard.review import CheckStep, JudgeCheck, JudgeRequest, Review, Reviewer, Verdict
from codeguard.working_tree import AllLines, ChangedLines


def reviewer(repo, judge, binding) -> Reviewer:
    local = Ruleset(name=None, root=repo.root / ".codeguard")
    return Reviewer(
        steps=(
            CheckStep(checks=(PatternRuleCheck(repo.root, local),)),
            CheckStep(checks=(JudgeCheck(binding, judge, 0.9),)),
        )
    )


class TestReviewer:
    def test_judge_runs_after_checks_on_files_that_passed(
        self, repo, make_diagnostic, make_violation, make_skill, make_binding
    ):
        repo.write("a.py", "print(1)\n")
        repo.write("b.py", "x = 1\n")
        judge = RecordingJudge(Verdict(violations=(make_violation(file="b.py"),)))

        result = reviewer(repo, judge, make_binding()).run(AllLines(("a.py", "b.py")))

        assert result == Review(
            diagnostics=(make_diagnostic(), make_diagnostic(judged=True, file="b.py"))
        )
        assert judge.received == [JudgeRequest(make_skill(), "b.py")]

    def test_violations_on_unchanged_lines_are_not_reported(
        self, repo, make_violation, make_binding
    ):
        repo.write("a.py", "print(1)\nx = 1\n")
        judge = RecordingJudge(Verdict(violations=(make_violation(line=1),)))

        result = reviewer(repo, judge, make_binding()).run(ChangedLines({"a.py": frozenset({2})}))

        assert result == Review(diagnostics=())

    def test_unchanged_line_error_does_not_block_the_judge(
        self, repo, make_diagnostic, make_violation, make_skill, make_binding
    ):
        repo.write("a.py", "print(1)\nx = 1\n")
        judge = RecordingJudge(Verdict(violations=(make_violation(line=2),)))

        result = reviewer(repo, judge, make_binding()).run(ChangedLines({"a.py": frozenset({2})}))

        assert result == Review(diagnostics=(make_diagnostic(judged=True, line=2),))
        assert judge.received == [JudgeRequest(make_skill(), "a.py")]
