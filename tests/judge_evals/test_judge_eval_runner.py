from dataclasses import dataclass
from pathlib import Path

import pytest
from factories.diagnostic import MakeViolation
from recording_judge import JudgeCreation, RecordingJudge, RecordingJudges

from codeguard.config import RulesetLoader
from codeguard.judge_evals import JudgeEvalRunner, JudgeFactory
from codeguard.review import JudgeRequest, Skill, Verdict
from codeguard.rule_tests import RuleTestResult

ENUM_SKILL = "# Enum usage\n\nPass the enum member, never a bare literal.\n"
CASE_DIR = ".codeguard/rule-evals/enum-usage"
EVAL_FILE = ".codeguard/rule-evals/enum-usage-eval.yml"


@pytest.fixture
def enum_rule(repo):
    repo.write(".codeguard/skills/enum-usage/SKILL.md", f"---\nname: enum-usage\n---\n{ENUM_SKILL}")
    repo.write(
        ".codeguard/bindings/enum-usage.yaml",
        'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\ntriggers: [any]\n'
        "model: claude-haiku-5-5\n",
    )
    repo.write(f"{CASE_DIR}/status.py", "ship(status='shipped')\n")


def run(repo, judge_eval: str, verdict: Verdict) -> RuleTestResult:
    repo.write(EVAL_FILE, judge_eval)
    judges = RecordingJudges(RecordingJudge(verdict))
    return JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), (judges,), 0.9).run()


@pytest.mark.usefixtures("enum_rule")
class TestJudgeEvalRunner:
    def test_judges_each_case_from_its_rule_directory(self, repo):
        repo.write(EVAL_FILE, "id: enum-usage\nvalid: [status.py]\n")
        judges = RecordingJudges(RecordingJudge())

        JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), (judges,), 0.9).run()

        assert judges.created == [JudgeCreation(repo.root / CASE_DIR, "claude-haiku-5-5")]
        assert judges.judge.received == [
            JudgeRequest(Skill(name="enum-usage", text=ENUM_SKILL), "status.py")
        ]

    def test_confident_violation_passes_an_invalid_case(self, repo, make_violation):
        verdict = Verdict(violations=(make_violation(file="status.py", confidence=0.9),))

        result = run(repo, "id: enum-usage\ninvalid: [status.py]\n", verdict)

        assert result == RuleTestResult()

    def test_violation_outside_the_triggers_fails_with_the_kinds_on_its_line(
        self, repo, make_violation
    ):
        repo.write(
            ".codeguard/bindings/enum-usage.yaml",
            'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\ntriggers: [class-header]\n',
        )
        verdict = Verdict(violations=(make_violation(file="status.py", line=1, confidence=0.9),))

        result = run(repo, "id: enum-usage\ninvalid: [status.py]\n", verdict)

        assert result == RuleTestResult(
            problems=(
                f"{CASE_DIR}/status.py: enum-usage violation on line 1 is outside the triggers "
                "class-header\n"
                "  Add one of the kinds on that line to triggers in its binding: "
                "call, code, module-statement, string-literal",
            )
        )

    def test_violation_inside_the_triggers_passes(self, repo, make_violation):
        repo.write(
            ".codeguard/bindings/enum-usage.yaml",
            'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\ntriggers: [string-literal]\n',
        )
        verdict = Verdict(violations=(make_violation(file="status.py", line=1, confidence=0.9),))

        result = run(repo, "id: enum-usage\ninvalid: [status.py]\n", verdict)

        assert result == RuleTestResult()

    def test_unconfident_violation_fails_an_invalid_case(self, repo, make_violation):
        violation = make_violation(
            file="status.py", line=1, message="Pass the member.", confidence=0.6
        )

        result = run(
            repo, "id: enum-usage\ninvalid: [status.py]\n", Verdict(violations=(violation,))
        )

        assert result == RuleTestResult(
            problems=(
                f"{CASE_DIR}/status.py: "
                "enum-usage expected a violation with confidence 0.90, got:\n"
                "  line 1 (0.60): Pass the member.",
            ),
        )

    def test_no_violation_fails_an_invalid_case(self, repo):
        result = run(repo, "id: enum-usage\ninvalid: [status.py]\n", Verdict(violations=()))

        assert result == RuleTestResult(
            problems=(f"{CASE_DIR}/status.py: enum-usage expected a violation, got none",),
        )

    def test_violation_in_another_file_does_not_pass_an_invalid_case(self, repo, make_violation):
        verdict = Verdict(violations=(make_violation(file="other.py"),))

        result = run(repo, "id: enum-usage\ninvalid: [status.py]\n", verdict)

        assert result == RuleTestResult(
            problems=(f"{CASE_DIR}/status.py: enum-usage expected a violation, got none",),
        )

    def test_no_violation_passes_a_valid_case(self, repo):
        result = run(repo, "id: enum-usage\nvalid: [status.py]\n", Verdict(violations=()))

        assert result == RuleTestResult()

    def test_any_violation_fails_a_valid_case(self, repo, make_violation):
        violation = make_violation(
            file="status.py", line=1, message="Pass the member.", confidence=0.3
        )

        result = run(repo, "id: enum-usage\nvalid: [status.py]\n", Verdict(violations=(violation,)))

        assert result == RuleTestResult(
            problems=(
                f"{CASE_DIR}/status.py: enum-usage expected no violation, got:\n"
                "  line 1 (0.30): Pass the member.",
            ),
        )

    def test_missing_case_file_fails(self, repo):
        result = run(repo, "id: enum-usage\nvalid: [missing.py]\n", Verdict(violations=()))

        assert result == RuleTestResult(
            problems=(f"{CASE_DIR}/missing.py: enum-usage no such file",)
        )

    def test_unknown_rule_fails(self, repo):
        repo.write(
            ".codeguard/rule-evals/enum-usge-eval.yml", "id: enum-usge\nvalid: [status.py]\n"
        )
        judges = RecordingJudges(RecordingJudge())

        result = JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), (judges,), 0.9).run()

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


def run_variants(repo, runs, disable_skips="[]") -> RuleTestResult:
    repo.write(
        ".codeguard/bindings/enum-usage.yaml",
        'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\ntriggers: [any]\n'
        f"disable_skips: {disable_skips}\n",
    )
    repo.write(f"{CASE_DIR}/status.py", "# shipped\nstatus = 'shipped'\nship(status)\n")
    repo.write(EVAL_FILE, "id: enum-usage\nvalid: [status.py]\n")
    return JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), runs, 0.9).run()


@pytest.mark.usefixtures("enum_rule")
class TestVariants:
    def test_judges_each_variant_of_a_case(self, repo):
        judged: list[str] = []

        def reading(root: Path, model: str) -> FlagsText:
            judged.append((root / "status.py").read_text())
            return FlagsText("never", root)

        run_variants(repo, (reading,))

        assert sorted(judged) == [
            "\nstatus = 'shipped'\nship(status)\n",
            "# shipped\nname_1 = 'shipped'\nship(name_1)\n",
            "# shipped\nstatus = 'shipped'\nship(status)\n",
        ]

    def test_variant_with_another_verdict_fails_and_names_the_skip(self, repo):
        result = run_variants(repo, (flagging("name_1"),))

        assert result == RuleTestResult(
            problems=(
                f"{CASE_DIR}/status.py with its names renamed: "
                "enum-usage expected no violation, got:\n"
                "  line 1 (1.00): Rename it.\n"
                "  If enum-usage judges names, add renames to disable_skips in its binding.",
            ),
        )

    def test_failing_case_reports_only_its_own_failure(self, repo):
        result = run_variants(repo, (flagging("ship"),))

        assert result == RuleTestResult(
            problems=(
                f"{CASE_DIR}/status.py: enum-usage expected no violation, got:\n"
                "  line 1 (1.00): Rename it.",
            ),
        )

    def test_disabled_skip_has_no_variant(self, repo):
        result = run_variants(repo, (flagging("name_1"),), disable_skips="[renames]")

        assert result == RuleTestResult()


@pytest.mark.usefixtures("enum_rule")
class TestRepeats:
    def test_each_run_uses_its_own_judges(self, repo):
        first, second = RecordingJudges(RecordingJudge()), RecordingJudges(RecordingJudge())
        repo.write(EVAL_FILE, "id: enum-usage\nvalid: [status.py]\n")

        JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), (first, second), 0.9).run()

        assert (
            first.created
            == second.created
            == [JudgeCreation(repo.root / CASE_DIR, "claude-haiku-5-5")]
        )

    def test_failing_run_is_numbered(self, repo):
        repo.write(EVAL_FILE, "id: enum-usage\nvalid: [status.py]\n")
        runs = (RecordingJudges(RecordingJudge()), flagging("ship"))

        result = JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), runs, 0.9).run()

        assert result == RuleTestResult(
            problems=(
                f"{CASE_DIR}/status.py (run 2 of 2): enum-usage expected no violation, got:\n"
                "  line 1 (1.00): Rename it.",
            ),
        )


class TestWithoutJudgeEvals:
    def test_reports_nothing_without_loading_bindings(self, repo):
        repo.write(".codeguard/bindings/broken.yaml", "path: [a.py]\n")
        judges = RecordingJudges(RecordingJudge())

        result = JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), (judges,), 0.9).run()

        assert result == RuleTestResult()
