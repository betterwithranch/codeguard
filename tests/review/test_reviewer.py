from recording_judge import RecordingJudge

from codeguard.ast_grep import AstGrepCheck, Layout
from codeguard.review import CheckStep, JudgeCheck, JudgeRequest, Review, Reviewer, Verdict


class TestReviewer:
    def test_judge_runs_after_checks_on_files_that_passed(
        self, repo, make_diagnostic, make_violation, make_skill, make_binding
    ):
        repo.write("a.py", "print(1)\n")
        repo.write("b.py", "x = 1\n")
        judge = RecordingJudge(Verdict(violations=(make_violation(file="b.py"),)))
        reviewer = Reviewer(
            steps=(
                CheckStep(checks=(AstGrepCheck(Layout(repo.root)),)),
                CheckStep(checks=(JudgeCheck(make_binding(), judge),)),
            )
        )

        result = reviewer.run(["a.py", "b.py"])

        assert result == Review(
            diagnostics=(make_diagnostic(), make_diagnostic(judged=True, file="b.py"))
        )
        assert judge.received == [JudgeRequest(make_skill(), "b.py")]
