import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
from factories.diagnostic import MakeViolation
from recording_judge import FailingJudge, RecordingJudge, RecordingJudges

from codeguard.config import ConfigError, JudgeModel, JudgeProvider, RulesetLoader
from codeguard.judge_evals import JudgeEvalResult, JudgeEvalRunner, JudgeFactory
from codeguard.review import Judge, Judgement, JudgeRequest, Skill, Verdict
from codeguard.rule_tests import RuleTestResult

ENUM_SKILL = "# Enum usage\n\nPass the enum member, never a bare literal.\n"
EVAL_FILE = ".codeguard/rule-evals/enum-usage.yaml"
HAIKU = JudgeModel(provider=JudgeProvider.CLAUDE_CLI, name="claude-haiku-5-5")


def case(name: str, outcome: str, after: str = "ship(status='shipped')\n") -> str:
    indented = "".join(f"      {line}\n" for line in after.splitlines())
    return (
        f"  - name: {name}\n"
        f"    inputs:\n"
        f"      after: |\n  {indented.replace(chr(10) + '      ', chr(10) + '        ')}"
        f"    expected_output:\n"
        f"      outcome: {outcome}\n"
    )


def dataset(*cases: str) -> str:
    return "name: enum-usage\ncases:\n" + "".join(cases)


@pytest.fixture
def enum_rule(repo):
    repo.write(".codeguard/skills/enum-usage/SKILL.md", f"---\nname: enum-usage\n---\n{ENUM_SKILL}")
    repo.write(
        ".codeguard/bindings/enum-usage.yaml",
        'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\ntriggers: [any]\n'
        "model: claude-haiku-5-5\n",
    )


def run(repo, judge_eval: str, verdict: Verdict) -> JudgeEvalResult:
    repo.write(EVAL_FILE, judge_eval)
    judges = RecordingJudges(RecordingJudge(verdict))
    return JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()


@dataclass
class ReadingJudges:
    judged: list[tuple[JudgeModel, str]]

    def __call__(self, root: Path, model: JudgeModel) -> Judge:
        self.judged.append((model, (root / "status.py").read_text()))
        return RecordingJudge()


@dataclass
class ListingJudges:
    listed: list[list[str]]

    def __call__(self, root: Path, model: JudgeModel) -> Judge:
        self.listed.append(sorted(git(root, "ls-files", "--cached", "--others").split()))
        return RecordingJudge()


def git(directory: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=directory, check=True, capture_output=True, text=True
    ).stdout


@pytest.mark.usefixtures("enum_rule")
class TestJudgeEvalRunner:
    def test_judges_the_file_after_each_judged_edit(self, repo):
        repo.write(
            EVAL_FILE,
            "name: enum-usage\n"
            "cases:\n"
            "  - name: passes a string\n"
            "    inputs:\n"
            "      file: status.py\n"
            "      before: |\n"
            "        ship(status=Status.SHIPPED)\n"
            "      after: |\n"
            "        ship(status='shipped')\n"
            "    expected_output: {outcome: invalid}\n"
            "  - name: passes the member\n"
            "    inputs:\n"
            "      file: status.py\n"
            "      after: |\n"
            "        ship(status=Status.SHIPPED)\n"
            "    expected_output: {outcome: valid}\n",
        )
        judges = ReadingJudges([])

        JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert sorted(judges.judged) == [
            (HAIKU, "ship(status='shipped')\n"),
            (HAIKU, "ship(status=Status.SHIPPED)\n"),
        ]

    def test_judges_the_case_file_with_the_rule_skill(self, repo):
        repo.write(EVAL_FILE, dataset(case("passes a string", "valid")))
        judges = RecordingJudges(RecordingJudge())

        JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert judges.judge.received == [
            JudgeRequest(
                Skill(name="enum-usage", text=ENUM_SKILL),
                "module.py",
                "     1\tship(status='shipped')\n",
            )
        ]

    def test_each_case_is_judged_in_a_repository_holding_its_files(self, repo):
        repo.write(
            EVAL_FILE,
            "cases:\n"
            "  - name: passes a string\n"
            "    inputs:\n"
            "      file: shipping/ship.py\n"
            "      after: |\n"
            "        ship(status='shipped')\n"
            "      unchanged:\n"
            "        shipping/__init__.py: |\n"
            "          from shipping.status import Status\n"
            "    expected_output: {outcome: invalid}\n"
            "  - name: passes the member\n"
            "    inputs:\n"
            "      file: cancelling.py\n"
            "      after: |\n"
            "        cancel(status=Status.CANCELLED)\n"
            "    expected_output: {outcome: valid}\n",
        )
        judges = ListingJudges([])

        JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert sorted(judges.listed) == [
            ["cancelling.py"],
            ["shipping/__init__.py", "shipping/ship.py"],
        ]

    def test_judges_only_the_function_an_edit_changes(self, repo):
        repo.write(
            EVAL_FILE,
            "cases:\n"
            "  - name: passes a string\n"
            "    inputs:\n"
            "      file: status.py\n"
            "      before: |\n"
            "        def ship_order():\n"
            "            ship(status=Status.SHIPPED)\n"
            "\n"
            "\n"
            "        def cancel_order():\n"
            "            cancel(status=Status.CANCELLED)\n"
            "      after: |\n"
            "        def ship_order():\n"
            "            ship(status=Status.SHIPPED)\n"
            "\n"
            "\n"
            "        def cancel_order():\n"
            "            cancel(status='cancelled')\n"
            "    expected_output: {outcome: invalid}\n",
        )
        judges = RecordingJudges(RecordingJudge())

        JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert judges.judge.received == [
            JudgeRequest(
                Skill(name="enum-usage", text=ENUM_SKILL),
                "status.py",
                "     5\tdef cancel_order():\n     6\t    cancel(status='cancelled')\n",
            )
        ]

    def test_reports_one_experiment_per_rule_named_after_the_rule_and_model(self, repo):
        result = run(repo, dataset(case("passes a string", "valid")), Verdict(violations=()))

        assert [(report.dataset_name, report.name) for report in result.reports] == [
            ("enum-usage", "enum-usage on claude-haiku-5-5")
        ]

    def test_confident_violation_passes_an_invalid_case(self, repo, make_violation):
        verdict = Verdict(violations=(make_violation(file="module.py", confidence=0.9),))

        result = run(repo, dataset(case("passes a string", "invalid")), verdict)

        assert result.passed

    def test_violation_outside_the_triggers_fails_with_the_kinds_on_its_line(
        self, repo, make_violation
    ):
        repo.write(
            ".codeguard/bindings/enum-usage.yaml",
            'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\n'
            "triggers: [class-header, string-literal]\n",
        )
        verdict = Verdict(violations=(make_violation(file="module.py", line=2, confidence=0.9),))

        result = run(
            repo,
            dataset(case("passes a string", "invalid", "ship(status='shipped')\ncount = 1\n")),
            verdict,
        )

        assert result.failures == (
            "enum-usage passes a string: violation on line 2 is outside the "
            "triggers class-header, string-literal\n"
            "  Add one of the kinds on that line to triggers in its binding: "
            "code, module-statement, number-literal",
        )

    def test_violation_outside_the_triggers_in_a_valid_case_fails_only_as_a_false_positive(
        self, repo, make_violation
    ):
        repo.write(
            ".codeguard/bindings/enum-usage.yaml",
            'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\ntriggers: [string-literal]\n',
        )
        verdict = Verdict(violations=(make_violation(file="module.py", line=2, confidence=0.9),))

        result = run(
            repo,
            dataset(case("passes a string", "valid", "ship(status='shipped')\ncount = 1\n")),
            verdict,
        )

        assert [failure.split("\n")[0] for failure in result.failures] == [
            "enum-usage passes a string: expected outcome valid, got outcome invalid"
        ]

    def test_dataset_without_cases_fails_with_its_name(self, repo):
        result = run(repo, "name: enum-usage\ncases: []\n", Verdict(violations=()))

        assert not result.passed
        assert result.failures == ("enum-usage: no case was evaluated",)

    def test_violation_inside_the_triggers_passes(self, repo, make_violation):
        repo.write(
            ".codeguard/bindings/enum-usage.yaml",
            'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\ntriggers: [string-literal]\n',
        )
        verdict = Verdict(violations=(make_violation(file="module.py", confidence=0.9),))

        result = run(repo, dataset(case("passes a string", "invalid")), verdict)

        assert result.passed

    def test_unconfident_violation_fails_an_invalid_case(self, repo, make_violation):
        violation = make_violation(file="module.py", message="Pass the member.", confidence=0.6)

        result = run(
            repo, dataset(case("passes a string", "invalid")), Verdict(violations=(violation,))
        )

        assert result.failures == (
            "enum-usage passes a string: expected outcome invalid, got outcome uncertain\n"
            "  line 1 (0.60): Pass the member.",
        )

    def test_no_violation_fails_an_invalid_case(self, repo):
        result = run(repo, dataset(case("passes a string", "invalid")), Verdict(violations=()))

        assert result.failures == (
            "enum-usage passes a string: expected outcome invalid, got outcome valid",
        )

    def test_violation_in_another_file_does_not_pass_an_invalid_case(self, repo, make_violation):
        verdict = Verdict(violations=(make_violation(file="other.py"),))

        result = run(repo, dataset(case("passes a string", "invalid")), verdict)

        assert result.failures == (
            "enum-usage passes a string: expected outcome invalid, got outcome valid",
        )

    def test_no_violation_passes_a_valid_case(self, repo):
        result = run(repo, dataset(case("passes a string", "valid")), Verdict(violations=()))

        assert result.passed

    def test_any_violation_fails_a_valid_case(self, repo, make_violation):
        violation = make_violation(file="module.py", message="Pass the member.", confidence=0.3)

        result = run(
            repo, dataset(case("passes a string", "valid")), Verdict(violations=(violation,))
        )

        assert result.failures == (
            "enum-usage passes a string: expected outcome valid, got outcome uncertain\n"
            "  line 1 (0.30): Pass the member.",
        )

    def test_case_outside_the_triggers_is_skipped_without_judging(self, repo):
        repo.write(
            ".codeguard/bindings/enum-usage.yaml",
            'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\ntriggers: [string-literal]\n',
        )
        repo.write(EVAL_FILE, dataset(case("counts", "skipped", "count = 1\n")))
        judges = RecordingJudges(RecordingJudge())

        result = JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert (result.passed, judges.created) == (True, [])

    def test_invalid_case_outside_the_triggers_fails_as_skipped(self, repo):
        repo.write(
            ".codeguard/bindings/enum-usage.yaml",
            'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\ntriggers: [string-literal]\n',
        )

        result = run(
            repo, dataset(case("counts", "invalid", "count = 1\n")), Verdict(violations=())
        )

        assert result.failures == (
            "enum-usage counts: expected outcome invalid, got outcome skipped",
        )

    def test_judge_error_fails_the_case(self, repo):
        repo.write(EVAL_FILE, dataset(case("passes a string", "invalid")))
        judges = RecordingJudges(FailingJudge())

        result = JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert result.failures == (
            "enum-usage passes a string: not judged: "
            "JudgeError: gemini failed with 502: upstream request failed",
        )

    def test_judge_error_does_not_pass(self, repo):
        repo.write(EVAL_FILE, dataset(case("passes a string", "invalid")))
        judges = RecordingJudges(FailingJudge())

        result = JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert not result.passed

    def test_unknown_rule_fails(self, repo):
        repo.write(
            ".codeguard/rule-evals/enum-usge.yaml",
            "name: enum-usge\ncases:\n" + case("passes a string", "valid"),
        )
        judges = RecordingJudges(RecordingJudge())

        result = JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert result == JudgeEvalResult(
            checks=RuleTestResult(
                problems=(".codeguard/rule-evals/enum-usge.yaml: no judge rule enum-usge",)
            )
        )

    def test_dataset_name_defaults_to_the_file_name(self, repo):
        repo.write(EVAL_FILE, "cases:\n" + case("passes a string", "valid"))

        result = run(repo, "cases:\n" + case("passes a string", "valid"), Verdict(violations=()))

        assert [report.dataset_name for report in result.reports] == ["enum-usage"]

    def test_case_without_expected_output_is_invalid(self, repo):
        repo.write(
            EVAL_FILE,
            "name: enum-usage\ncases:\n  - name: passes a string\n    inputs:\n      after: x\n",
        )
        judges = RecordingJudges(RecordingJudge())

        with pytest.raises(ConfigError) as error:
            JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert str(error.value) == (
            f"{repo.root / EVAL_FILE} is invalid:\n  cases.0.expected_output: Field required"
        )

    def test_case_without_a_name_is_invalid(self, repo):
        repo.write(
            EVAL_FILE,
            "name: enum-usage\ncases:\n  - inputs:\n      after: x\n"
            "    expected_output: {outcome: valid}\n",
        )
        judges = RecordingJudges(RecordingJudge())

        with pytest.raises(ConfigError) as error:
            JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert (
            str(error.value)
            == f"{repo.root / EVAL_FILE} is invalid:\n  cases.0.name: Field required"
        )

    def test_cases_with_the_same_name_are_invalid(self, repo):
        repo.write(
            EVAL_FILE, dataset(case("passes a string", "valid"), case("passes a string", "valid"))
        )
        judges = RecordingJudges(RecordingJudge())

        with pytest.raises(ConfigError) as error:
            JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert str(error.value) == (
            f"{repo.root / EVAL_FILE} is invalid:\n"
            "  cases: Value error, cases share a name: passes a string"
        )

    def test_evaluators_are_invalid(self, repo):
        repo.write(
            EVAL_FILE,
            dataset(case("passes a string", "valid")) + "evaluators:\n  - EqualsExpected\n",
        )
        judges = RecordingJudges(RecordingJudge())

        with pytest.raises(ConfigError) as error:
            JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert str(error.value) == (
            f"{repo.root / EVAL_FILE} is invalid:\n  evaluators: Extra inputs are not permitted"
        )

    def test_eval_file_named_yml_is_an_error(self, repo):
        repo.write(".codeguard/rule-evals/enum-usage-eval.yml", "cases: []\n")
        judges = RecordingJudges(RecordingJudge())

        with pytest.raises(ConfigError) as error:
            JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert str(error.value) == (
            "rule evals are <rule id>.yaml files; rename or convert:\n"
            f"  {repo.root}/.codeguard/rule-evals/enum-usage-eval.yml"
        )


@dataclass(frozen=True)
class FlagsText:
    text: str

    identity = "flags-text"

    def judge(self, request: JudgeRequest) -> Judgement:
        if self.text not in request.changes:
            return Judgement(Verdict(violations=()))
        violation = MakeViolation(file=request.file, message="Rename it.")
        return Judgement(Verdict(violations=(violation,)))


def flagging(text: str) -> JudgeFactory:
    return lambda root, model: FlagsText(text)


@pytest.mark.usefixtures("enum_rule")
class TestRepeats:
    def test_judges_each_case_once_per_repeat(self, repo):
        repo.write(EVAL_FILE, dataset(case("passes a string", "valid")))
        judges = RecordingJudges(RecordingJudge())

        JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9, repeat=3).run()

        assert [creation.model for creation in judges.created] == [HAIKU] * 3

    def test_failing_run_is_numbered(self, repo):
        repo.write(EVAL_FILE, dataset(case("passes a string", "valid")))

        result = JudgeEvalRunner(
            repo.root, RulesetLoader.local(repo.root), flagging("ship"), 0.9, repeat=2
        ).run()

        assert sorted(result.failures) == [
            f"enum-usage passes a string [{run}/2]: expected outcome valid, got outcome "
            "invalid\n  line 1 (1.00): Rename it."
            for run in (1, 2)
        ]


class TestWithoutJudgeEvals:
    def test_reports_nothing_without_loading_bindings(self, repo):
        repo.write(".codeguard/bindings/broken.yaml", "path: [a.py]\n")
        judges = RecordingJudges(RecordingJudge())

        result = JudgeEvalRunner(repo.root, RulesetLoader.local(repo.root), judges, 0.9).run()

        assert result == JudgeEvalResult()
