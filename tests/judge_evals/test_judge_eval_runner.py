from dataclasses import dataclass
from pathlib import Path

import pytest
from factories.diagnostic import MakeViolation
from recording_judge import FailingJudge, RecordingJudge, RecordingJudges

from codeguard.config import RulesetLoader
from codeguard.judge_evals import JudgeEvalRunner, JudgeFactory
from codeguard.review import Judge, JudgeRequest, Skill, Verdict
from codeguard.rule_tests import RuleTestResult

ENUM_SKILL = "# Enum usage\n\nPass the enum member, never a bare literal.\n"
EVAL_FILE = ".codeguard/rule-evals/enum-usage-eval.yml"
STATUS_CASE = "  - after: |\n      ship(status='shipped')\n"


@pytest.fixture
def enum_rule(repo):
    repo.write(".codeguard/skills/enum-usage/SKILL.md", f"---\nname: enum-usage\n---\n{ENUM_SKILL}")
    repo.write(
        ".codeguard/bindings/enum-usage.yaml",
        'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\ntriggers: [any]\n'
        "model: claude-haiku-5-5\n",
    )


def run(repo, judge_eval: str, verdict: Verdict) -> RuleTestResult:
    repo.write(EVAL_FILE, judge_eval)
    judges = RecordingJudges(RecordingJudge(verdict))
    return JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()


@dataclass
class ReadingJudges:
    judged: list[tuple[str, str]]

    def __call__(self, root: Path, model: str) -> Judge:
        self.judged.append((model, (root / "status.py").read_text()))
        return RecordingJudge()


@pytest.mark.usefixtures("enum_rule")
class TestJudgeEvalRunner:
    def test_judges_the_file_after_each_invalid_and_valid_edit(self, repo):
        repo.write(
            EVAL_FILE,
            "id: enum-usage\n"
            "invalid:\n"
            "  - file: status.py\n"
            "    before: |\n"
            "      ship(status=Status.SHIPPED)\n"
            "    after: |\n"
            "      ship(status='shipped')\n"
            "valid:\n"
            "  - file: status.py\n"
            "    after: |\n"
            "      ship(status=Status.SHIPPED)\n"
            "skipped:\n"
            "  - file: status.py\n"
            "    after: |\n"
            "      count = 1\n",
        )
        judges = ReadingJudges([])

        JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert sorted(judges.judged) == [
            ("claude-haiku-5-5", "ship(status='shipped')\n"),
            ("claude-haiku-5-5", "ship(status=Status.SHIPPED)\n"),
        ]

    def test_judges_the_case_file_with_the_rule_skill(self, repo):
        repo.write(EVAL_FILE, f"id: enum-usage\nvalid:\n{STATUS_CASE}")
        judges = RecordingJudges(RecordingJudge())

        JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert judges.judge.received == [
            JudgeRequest(Skill(name="enum-usage", text=ENUM_SKILL), "module.py")
        ]

    def test_confident_violation_passes_an_invalid_case(self, repo, make_violation):
        verdict = Verdict(violations=(make_violation(file="module.py", confidence=0.9),))

        result = run(repo, f"id: enum-usage\ninvalid:\n{STATUS_CASE}", verdict)

        assert result == RuleTestResult()

    def test_violation_outside_the_triggers_fails_with_the_kinds_on_its_line(
        self, repo, make_violation
    ):
        repo.write(
            ".codeguard/bindings/enum-usage.yaml",
            'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\ntriggers: [class-header]\n',
        )
        verdict = Verdict(violations=(make_violation(file="module.py", confidence=0.9),))

        result = run(repo, f"id: enum-usage\ninvalid:\n{STATUS_CASE}", verdict)

        assert result == RuleTestResult(
            problems=(
                f"{EVAL_FILE} invalid case 1: enum-usage violation on line 1 is outside the "
                "triggers class-header\n"
                "  Add one of the kinds on that line to triggers in its binding: "
                "call, code, module-statement, string-literal",
            )
        )

    def test_violation_inside_the_triggers_passes(self, repo, make_violation):
        repo.write(
            ".codeguard/bindings/enum-usage.yaml",
            'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\ntriggers: [string-literal]\n',
        )
        verdict = Verdict(violations=(make_violation(file="module.py", confidence=0.9),))

        result = run(repo, f"id: enum-usage\ninvalid:\n{STATUS_CASE}", verdict)

        assert result == RuleTestResult()

    def test_unconfident_violation_fails_an_invalid_case(self, repo, make_violation):
        violation = make_violation(file="module.py", message="Pass the member.", confidence=0.6)

        result = run(
            repo, f"id: enum-usage\ninvalid:\n{STATUS_CASE}", Verdict(violations=(violation,))
        )

        assert result == RuleTestResult(
            problems=(
                f"{EVAL_FILE} invalid case 1: "
                "enum-usage expected a violation with confidence 0.90, got:\n"
                "  line 1 (0.60): Pass the member.",
            ),
        )

    def test_no_violation_fails_an_invalid_case(self, repo):
        result = run(repo, f"id: enum-usage\ninvalid:\n{STATUS_CASE}", Verdict(violations=()))

        assert result == RuleTestResult(
            problems=(f"{EVAL_FILE} invalid case 1: enum-usage expected a violation, got none",),
        )

    def test_violation_in_another_file_does_not_pass_an_invalid_case(self, repo, make_violation):
        verdict = Verdict(violations=(make_violation(file="other.py"),))

        result = run(repo, f"id: enum-usage\ninvalid:\n{STATUS_CASE}", verdict)

        assert result == RuleTestResult(
            problems=(f"{EVAL_FILE} invalid case 1: enum-usage expected a violation, got none",),
        )

    def test_no_violation_passes_a_valid_case(self, repo):
        result = run(repo, f"id: enum-usage\nvalid:\n{STATUS_CASE}", Verdict(violations=()))

        assert result == RuleTestResult()

    def test_any_violation_fails_a_valid_case(self, repo, make_violation):
        violation = make_violation(file="module.py", message="Pass the member.", confidence=0.3)

        result = run(
            repo, f"id: enum-usage\nvalid:\n{STATUS_CASE}", Verdict(violations=(violation,))
        )

        assert result == RuleTestResult(
            problems=(
                f"{EVAL_FILE} valid case 1: enum-usage expected no violation, got:\n"
                "  line 1 (0.30): Pass the member.",
            ),
        )

    def test_skipped_case_is_not_judged(self, repo):
        repo.write(EVAL_FILE, f"id: enum-usage\nskipped:\n{STATUS_CASE}")
        judges = RecordingJudges(RecordingJudge())

        JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert judges.created == []

    def test_judge_error_fails_the_case(self, repo):
        repo.write(EVAL_FILE, f"id: enum-usage\ninvalid:\n{STATUS_CASE}")
        judges = RecordingJudges(FailingJudge())

        result = JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert result == RuleTestResult(
            problems=(
                f"{EVAL_FILE} invalid case 1: enum-usage not judged: "
                "JudgeError: gemini failed with 502: upstream request failed",
            )
        )

    def test_unknown_rule_fails(self, repo):
        repo.write(
            ".codeguard/rule-evals/enum-usge-eval.yml", f"id: enum-usge\nvalid:\n{STATUS_CASE}"
        )
        judges = RecordingJudges(RecordingJudge())

        result = JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert result == RuleTestResult(
            problems=(".codeguard/rule-evals/enum-usge-eval.yml: no judge rule enum-usge",),
        )


@dataclass(frozen=True)
class FlagsText:
    text: str
    root: Path

    identity = "flags-text"

    def judge(self, request: JudgeRequest) -> Verdict:
        if self.text not in (self.root / request.file).read_text():
            return Verdict(violations=())
        violation = MakeViolation(file=request.file, message="Rename it.")
        return Verdict(violations=(violation,))


def flagging(text: str) -> JudgeFactory:
    return lambda root, model: FlagsText(text, root)


@pytest.mark.usefixtures("enum_rule")
class TestRepeats:
    def test_judges_each_case_once_per_repeat(self, repo):
        repo.write(EVAL_FILE, f"id: enum-usage\nvalid:\n{STATUS_CASE}")
        judges = RecordingJudges(RecordingJudge())

        JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9, repeat=3).run()

        assert [creation.model for creation in judges.created] == ["claude-haiku-5-5"] * 3

    def test_failing_run_is_numbered(self, repo):
        repo.write(EVAL_FILE, f"id: enum-usage\nvalid:\n{STATUS_CASE}")

        result = JudgeEvalRunner(
            repo.root, RulesetLoader.local(repo.root), flagging("ship"), 0.9, repeat=2
        ).run()

        assert sorted(result.problems) == [
            f"{EVAL_FILE} valid case 1 [{run}/2]: enum-usage expected no violation, got:\n"
            "  line 1 (1.00): Rename it."
            for run in (1, 2)
        ]


class TestWithoutJudgeEvals:
    def test_reports_nothing_without_loading_bindings(self, repo):
        repo.write(".codeguard/bindings/broken.yaml", "path: [a.py]\n")
        judges = RecordingJudges(RecordingJudge())

        result = JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert result == RuleTestResult()
