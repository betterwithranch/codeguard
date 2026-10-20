import pytest

from codeguard.config import RulesetLoader
from codeguard.judge_evals import EvalCoverage
from codeguard.rule_tests import RuleTestResult

ENUM_SKILL = "# Enum usage\n\nPass the enum member, never a bare literal.\n"
INVALID_EVAL = "id: enum-usage\ninvalid:\n  - after: |\n      ship('shipped')\n"


@pytest.fixture
def enum_rule(repo):
    repo.write(".codeguard/skills/enum-usage/SKILL.md", f"---\nname: enum-usage\n---\n{ENUM_SKILL}")
    repo.write(
        ".codeguard/bindings/enum-usage.yaml",
        'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\ntriggers: [any]\n',
    )


@pytest.mark.usefixtures("enum_rule")
class TestEvalCoverage:
    def test_judge_rule_without_an_invalid_case_fails(self, repo):
        result = EvalCoverage(RulesetLoader.local(repo.root)).run()

        assert result == RuleTestResult(problems=("enum-usage: no eval with an invalid case",))

    def test_judge_rule_with_an_invalid_case_passes(self, repo):
        repo.write(".codeguard/rule-evals/enum-usage-eval.yml", INVALID_EVAL)

        assert EvalCoverage(RulesetLoader.local(repo.root)).run() == RuleTestResult()

    def test_judge_rule_with_only_a_valid_case_fails(self, repo):
        repo.write(
            ".codeguard/rule-evals/enum-usage-eval.yml",
            "id: enum-usage\nvalid:\n  - after: |\n      ship(Status.SHIPPED)\n",
        )

        result = EvalCoverage(RulesetLoader.local(repo.root)).run()

        assert result == RuleTestResult(problems=("enum-usage: no eval with an invalid case",))
