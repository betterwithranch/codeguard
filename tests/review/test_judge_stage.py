from recording_judge import RecordingJudge

from codeguard.config import Binding, Config
from codeguard.review import Concern, JudgeStage


class TestRun:
    def test_file_with_blocking_finding_is_not_judged(self, make_finding, make_skill):
        judge = RecordingJudge()
        config = Config(bindings=(Binding(skill=make_skill(), paths=("**",)),))

        JudgeStage(judge=judge, selector=config).run(["a.py", "b.py"], (make_finding(),))

        assert judge.received == [Concern(skill=make_skill(), files=("b.py",))]

    def test_file_with_only_a_warning_is_judged(self, make_finding, make_skill):
        judge = RecordingJudge()
        config = Config(bindings=(Binding(skill=make_skill(), paths=("**",)),))

        JudgeStage(judge=judge, selector=config).run(["a.py"], (make_finding(warning=True),))

        assert judge.received == [Concern(skill=make_skill(), files=("a.py",))]
