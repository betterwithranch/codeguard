from recording_judge import RecordingJudge

from codeguard.ast_grep import AstGrepCheck, Layout
from codeguard.config import Binding, Config
from codeguard.review import CheckStage, Concern, JudgeStage, Review, Reviewer


class TestRun:
    def test_judge_runs_after_checks_on_files_that_passed(self, repo, make_finding, make_skill):
        repo.write("a.py", "print(1)\n")
        repo.write("b.py", "x = 1\n")
        judged = make_finding(rule="responsibility-placement", file="b.py", note=None)
        judge = RecordingJudge(findings=(judged,))
        config = Config(bindings=(Binding(skill=make_skill(), paths=("**",)),))
        reviewer = Reviewer(
            stages=(
                CheckStage(checks=(AstGrepCheck(Layout(repo.root)),)),
                JudgeStage(judge=judge, selector=config),
            )
        )

        result = reviewer.run(["a.py", "b.py"])

        assert result == Review(findings=(make_finding(), judged))
        assert judge.received == [Concern(skill=make_skill(), files=("b.py",))]
