import pytest
from recording_judge import JudgeCreation, RecordingJudge, RecordingJudges

from codeguard.config import RulesetLoader
from codeguard.judge_evals import EvalResult, JudgeEvalRunner
from codeguard.review import JudgeRequest, Skill, Verdict

ENUM_SKILL = "# Enum usage\n\nPass the enum member, never a bare literal.\n"
CASE_DIR = ".codeguard/rule-evals/enum-usage"
EVAL_FILE = ".codeguard/rule-evals/enum-usage-eval.yml"


@pytest.fixture
def enum_rule(repo):
    repo.write(".codeguard/skills/enum-usage/SKILL.md", f"---\nname: enum-usage\n---\n{ENUM_SKILL}")
    repo.write(
        ".codeguard/bindings/enum-usage.yaml",
        'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\nmodel: claude-haiku-5-5\n',
    )
    repo.write(f"{CASE_DIR}/status.py", "ship(status='shipped')\n")


def run(repo, judge_eval: str, verdict: Verdict) -> EvalResult:
    repo.write(EVAL_FILE, judge_eval)
    judges = RecordingJudges(RecordingJudge(verdict))
    return JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()


@pytest.mark.usefixtures("enum_rule")
class TestJudgeEvalRunner:
    def test_judges_each_case_from_its_rule_directory(self, repo):
        repo.write(EVAL_FILE, "id: enum-usage\nvalid: [status.py]\n")
        judges = RecordingJudges(RecordingJudge())

        JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert judges.created == [JudgeCreation(repo.root / CASE_DIR, "claude-haiku-5-5")]
        assert judges.judge.received == [
            JudgeRequest(Skill(name="enum-usage", text=ENUM_SKILL), "status.py")
        ]

    def test_confident_violation_passes_an_invalid_case(self, repo, make_violation):
        verdict = Verdict(violations=(make_violation(file="status.py", confidence=0.9),))

        result = run(repo, "id: enum-usage\ninvalid: [status.py]\n", verdict)

        assert result == EvalResult()

    def test_unconfident_violation_fails_an_invalid_case(self, repo, make_violation):
        violation = make_violation(
            file="status.py", line=1, message="Pass the member.", confidence=0.6
        )

        result = run(
            repo, "id: enum-usage\ninvalid: [status.py]\n", Verdict(violations=(violation,))
        )

        assert result == EvalResult(
            problems=(
                f"{CASE_DIR}/status.py: "
                "enum-usage expected a violation with confidence 0.90, got:\n"
                "  line 1 (0.60): Pass the member.",
            ),
        )

    def test_no_violation_fails_an_invalid_case(self, repo):
        result = run(repo, "id: enum-usage\ninvalid: [status.py]\n", Verdict(violations=()))

        assert result == EvalResult(
            problems=(f"{CASE_DIR}/status.py: enum-usage expected a violation, got none",),
        )

    def test_violation_in_another_file_does_not_pass_an_invalid_case(self, repo, make_violation):
        verdict = Verdict(violations=(make_violation(file="other.py"),))

        result = run(repo, "id: enum-usage\ninvalid: [status.py]\n", verdict)

        assert result == EvalResult(
            problems=(f"{CASE_DIR}/status.py: enum-usage expected a violation, got none",),
        )

    def test_no_violation_passes_a_valid_case(self, repo):
        result = run(repo, "id: enum-usage\nvalid: [status.py]\n", Verdict(violations=()))

        assert result == EvalResult()

    def test_any_violation_fails_a_valid_case(self, repo, make_violation):
        violation = make_violation(
            file="status.py", line=1, message="Pass the member.", confidence=0.3
        )

        result = run(repo, "id: enum-usage\nvalid: [status.py]\n", Verdict(violations=(violation,)))

        assert result == EvalResult(
            problems=(
                f"{CASE_DIR}/status.py: enum-usage expected no violation, got:\n"
                "  line 1 (0.30): Pass the member.",
            ),
        )

    def test_missing_case_file_fails(self, repo):
        result = run(repo, "id: enum-usage\nvalid: [missing.py]\n", Verdict(violations=()))

        assert result == EvalResult(problems=(f"{CASE_DIR}/missing.py: enum-usage no such file",))

    def test_unknown_rule_fails(self, repo):
        repo.write(
            ".codeguard/rule-evals/enum-usge-eval.yml", "id: enum-usge\nvalid: [status.py]\n"
        )
        judges = RecordingJudges(RecordingJudge())

        result = JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert result == EvalResult(
            problems=(".codeguard/rule-evals/enum-usge-eval.yml: no judge rule enum-usge",),
        )


class TestWithoutJudgeEvals:
    def test_reports_nothing_without_loading_bindings(self, repo):
        repo.write(".codeguard/bindings/broken.yaml", "path: [a.py]\n")
        judges = RecordingJudges(RecordingJudge())

        result = JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert result == EvalResult()
