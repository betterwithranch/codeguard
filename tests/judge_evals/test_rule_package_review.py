import pytest
from recording_judge import RecordingJudge, RecordingJudges

from codeguard.config import RulesetLoader
from codeguard.judge_evals import RulePackageReview
from codeguard.review import Verdict
from codeguard.rule_tests import RuleTestResult

ENUM_SKILL = "# Enum usage\n\nPass the enum member, never a bare literal.\n"


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
        repo.write(".codeguard/rule-evals/enum-usage-eval.yml", "id: enum-usage\ninvalid: [a.py]\n")
        judges = RecordingJudges(RecordingJudge())

        result = RulePackageReview(RulesetLoader.local(repo.root), judges, 0.9).run()

        assert result == RuleTestResult()

    def test_reviews_the_skill_with_its_triggers_and_gates(self, repo):
        repo.write(".codeguard/rule-evals/enum-usage-eval.yml", "id: enum-usage\ninvalid: [a.py]\n")
        judge = RecordingJudge()

        RulePackageReview(RulesetLoader.local(repo.root), RecordingJudges(judge), 0.9).run()

        [request] = judge.received
        assert (request.skill.name, request.file) == ("rule-review", "rule.md")

    def test_confident_review_finding_fails_the_rule(self, repo, make_violation):
        repo.write(".codeguard/rule-evals/enum-usage-eval.yml", "id: enum-usage\ninvalid: [a.py]\n")
        finding = make_violation(file="rule.md", message="No gate matches enum members.")
        judges = RecordingJudges(RecordingJudge(Verdict(violations=(finding,))))

        result = RulePackageReview(RulesetLoader.local(repo.root), judges, 0.9).run()

        assert result == RuleTestResult(problems=("enum-usage: No gate matches enum members.",))
