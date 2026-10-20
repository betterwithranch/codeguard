from dataclasses import dataclass, field
from pathlib import Path

import pytest
from recording_judge import FailingJudge, RecordingJudge, RecordingJudges

from codeguard.config import RulesetLoader
from codeguard.judge_evals import RulePackageReview
from codeguard.review import JudgeRequest, Verdict
from codeguard.rule_tests import RuleTestResult

ENUM_SKILL = "# Enum usage\n\nPass the enum member, never a bare literal.\n"
INVALID_EVAL = "id: enum-usage\ninvalid:\n  - after: |\n      ship('shipped')\n"


@pytest.fixture
def enum_rule(repo):
    repo.write(".codeguard/skills/enum-usage/SKILL.md", f"---\nname: enum-usage\n---\n{ENUM_SKILL}")
    repo.write(
        ".codeguard/bindings/enum-usage.yaml",
        'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\ntriggers: [literal-argument]\n',
    )
    repo.write(
        ".codeguard/gates/literal-argument.yml",
        "id: literal-argument\nlanguage: python\nrule:\n  kind: string\n"
        "  inside: {kind: argument_list}\n",
    )


@pytest.mark.usefixtures("enum_rule")
class TestRulePackageReview:
    def test_judge_rule_without_an_invalid_case_fails(self, repo):
        judges = RecordingJudges(RecordingJudge())

        result = RulePackageReview(RulesetLoader.local(repo.root), judges, 0.9).run()

        assert result == RuleTestResult(problems=("enum-usage: no eval with an invalid case",))

    def test_judge_rule_with_an_invalid_case_passes(self, repo):
        repo.write(".codeguard/rule-evals/enum-usage-eval.yml", INVALID_EVAL)
        judges = RecordingJudges(RecordingJudge())

        result = RulePackageReview(RulesetLoader.local(repo.root), judges, 0.9).run()

        assert result == RuleTestResult()

    def test_reviews_the_rule_file_with_the_rule_review_skill(self, repo):
        repo.write(".codeguard/rule-evals/enum-usage-eval.yml", INVALID_EVAL)
        judge = RecordingJudge()

        RulePackageReview(RulesetLoader.local(repo.root), RecordingJudges(judge), 0.9).run()

        [request] = judge.received
        assert (request.skill.name, request.file) == ("rule-review", "rule.md")

    def test_judge_error_warns_without_failing_the_review(self, repo):
        repo.write(".codeguard/rule-evals/enum-usage-eval.yml", INVALID_EVAL)
        judges = RecordingJudges(FailingJudge())

        result = RulePackageReview(RulesetLoader.local(repo.root), judges, 0.9).run()

        assert result == RuleTestResult(
            warnings=(
                "enum-usage: rule review not judged: "
                "gemini failed with 502: upstream request failed",
            )
        )

    def test_confident_violation_fails_the_rule(self, repo, make_violation):
        repo.write(".codeguard/rule-evals/enum-usage-eval.yml", INVALID_EVAL)
        finding = make_violation(
            file="rule.md",
            message="`ship(Status.SHIPPED.value)` breaks it outside every trigger.",
            note="literal-argument leaves out attributes; no gate matches it.",
        )
        judges = RecordingJudges(RecordingJudge(Verdict(violations=(finding,))))

        result = RulePackageReview(RulesetLoader.local(repo.root), judges, 0.9).run()

        assert result == RuleTestResult(
            problems=(
                "enum-usage: `ship(Status.SHIPPED.value)` breaks it outside every trigger.\n"
                "  literal-argument leaves out attributes; no gate matches it.",
            )
        )


@dataclass(frozen=True)
class RuleFileJudge:
    root: Path
    read: list[str]
    identity: str = "rule-file"

    def judge(self, request: JudgeRequest) -> Verdict:
        self.read.append((self.root / request.file).read_text())
        return Verdict(violations=())


@dataclass(frozen=True)
class RuleFileJudges:
    read: list[str] = field(default_factory=list)

    def __call__(self, root: Path, model: str) -> RuleFileJudge:
        return RuleFileJudge(root, self.read)


def described(repo, triggers: str) -> str:
    repo.write(
        ".codeguard/bindings/enum-usage.yaml",
        f'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\ntriggers: [{triggers}]\n',
    )
    repo.write(".codeguard/rule-evals/enum-usage-eval.yml", INVALID_EVAL)
    repo.write(".codeguard/gates/class.yml", "id: class\nlanguage: python\nrule:\n  kind: class\n")
    judges = RuleFileJudges()
    RulePackageReview(RulesetLoader.local(repo.root), judges, 0.9).run()
    [description] = judges.read
    return description


@pytest.mark.usefixtures("enum_rule")
class TestRuleDescription:
    def test_sections_follow_the_skill(self, repo):
        description = described(repo, "literal-argument")

        headings = [line for line in description.splitlines() if line.startswith("## ")]
        assert headings == ["## Skill", "## Triggers", "## Other gates", "## Other change kinds"]

    def test_gate_trigger_has_its_rule(self, repo):
        description = described(repo, "literal-argument")

        assert (
            "### gate:literal-argument\n\nA gate. Its ast-grep rule:\n\n"
            "`{inside: {kind: argument_list}, kind: string}`"
        ) in description

    def test_other_gates_leave_out_the_triggers(self, repo):
        description = described(repo, "literal-argument")

        other_gates = description.split("## Other gates")[1].split("## Other change kinds")[0]
        assert other_gates.strip() == "- gate:class: `{kind: class}`"

    def test_change_kind_trigger_has_its_rule_by_language(self, repo):
        description = described(repo, "fixture")

        assert (
            "### fixture\n\nA built-in change kind. Its ast-grep rule by language:\n\n- python: `{"
            in description
        )

    def test_derived_change_kind_trigger_says_what_it_matches(self, repo):
        description = described(repo, "code")

        assert (
            "### code\n\nA built-in change kind. It matches every line that is not only a "
            "comment or docstring."
        ) in description

    def test_other_change_kinds_leave_out_the_triggers(self, repo):
        description = described(repo, "fixture, code")

        other_kinds = description.split("## Other change kinds\n\n")[1].strip().split(", ")
        assert "fixture" not in other_kinds
        assert "code" not in other_kinds
        assert "any" in other_kinds
