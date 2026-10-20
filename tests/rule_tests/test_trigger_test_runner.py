import pytest

from codeguard.config import RulesetLoader
from codeguard.rule_tests import RuleTestResult, TriggerTestRunner


@pytest.fixture
def enum_rule(repo):
    repo.write(
        ".codeguard/skills/enum-usage/SKILL.md", "---\nname: enum-usage\n---\n# Enum usage\n"
    )
    repo.write(
        ".codeguard/bindings/enum-usage.yaml",
        'skill: .codeguard/skills/enum-usage\npaths: ["**/*.py"]\n'
        'exclude_paths: ["**/test_*.py"]\ntriggers: [enum-value, definition-added-or-removed]\n',
    )
    repo.write(
        ".codeguard/gates/enum-value.yml",
        "id: enum-value\nlanguage: python\nrule:\n  pattern: $X.value\n",
    )


@pytest.mark.usefixtures("enum_rule")
class TestTriggerTestRunner:
    def test_triggered_case_whose_change_touches_a_gate_passes(self, repo):
        repo.write(
            ".codeguard/rule-tests/triggers/enum-usage-test.yml",
            "id: enum-usage\n"
            "triggered:\n"
            "  - before: |\n"
            "      label = status.name\n"
            "    after: |\n"
            "      label = status.value\n",
        )

        result = TriggerTestRunner(repo.root, RulesetLoader.local(repo.root)).run()

        assert result == RuleTestResult()

    def test_triggered_case_whose_change_misses_the_triggers_fails_with_the_touched_kinds(
        self, repo
    ):
        repo.write(
            ".codeguard/rule-tests/triggers/enum-usage-test.yml",
            "id: enum-usage\n"
            "triggered:\n"
            "  - before: |\n"
            "      label = status.value\n"
            "      count = 1\n"
            "    after: |\n"
            "      label = status.value\n"
            "      count = 2\n",
        )

        result = TriggerTestRunner(repo.root, RulesetLoader.local(repo.root)).run()

        assert result == RuleTestResult(
            problems=(
                ".codeguard/rule-tests/triggers/enum-usage-test.yml triggered case 1: enum-usage "
                "triggers definition-added-or-removed, gate:enum-value miss the change, which "
                "touches code, module-statement, number-literal",
            ),
        )

    def test_skipped_case_whose_change_touches_a_gate_fails(self, repo):
        repo.write(
            ".codeguard/rule-tests/triggers/enum-usage-test.yml",
            "id: enum-usage\nskipped:\n  - after: |\n      label = status.value\n",
        )

        result = TriggerTestRunner(repo.root, RulesetLoader.local(repo.root)).run()

        assert result == RuleTestResult(
            problems=(
                ".codeguard/rule-tests/triggers/enum-usage-test.yml skipped case 1: enum-usage "
                "triggers definition-added-or-removed, gate:enum-value fire on the change, which "
                "touches attribute-access, code, gate:enum-value, module-statement",
            ),
        )

    def test_skipped_case_whose_change_misses_the_triggers_passes(self, repo):
        repo.write(
            ".codeguard/rule-tests/triggers/enum-usage-test.yml",
            "id: enum-usage\n"
            "skipped:\n"
            "  - before: |\n"
            "      count = 1\n"
            "    after: |\n"
            "      count = 2\n",
        )

        result = TriggerTestRunner(repo.root, RulesetLoader.local(repo.root)).run()

        assert result == RuleTestResult()

    def test_triggered_case_whose_removed_function_touches_definition_added_or_removed_passes(
        self, repo
    ):
        repo.write(
            ".codeguard/rule-tests/triggers/enum-usage-test.yml",
            "id: enum-usage\n"
            "triggered:\n"
            "  - before: |\n"
            "      def total():\n"
            "          return 1\n"
            "\n"
            "\n"
            "      count = 1\n"
            "    after: |\n"
            "      count = 1\n",
        )

        result = TriggerTestRunner(repo.root, RulesetLoader.local(repo.root)).run()

        assert result == RuleTestResult()

    def test_case_file_outside_the_binding_paths_fails(self, repo):
        repo.write(
            ".codeguard/rule-tests/triggers/enum-usage-test.yml",
            "id: enum-usage\n"
            "triggered:\n"
            "  - file: tests/test_status.py\n"
            "    after: |\n"
            "      label = status.value\n",
        )

        result = TriggerTestRunner(repo.root, RulesetLoader.local(repo.root)).run()

        assert result == RuleTestResult(
            problems=(
                ".codeguard/rule-tests/triggers/enum-usage-test.yml triggered case 1: "
                "tests/test_status.py is outside the enum-usage paths",
            ),
        )

    def test_case_without_a_change_fails(self, repo):
        repo.write(
            ".codeguard/rule-tests/triggers/enum-usage-test.yml",
            "id: enum-usage\n"
            "triggered:\n"
            "  - before: |\n"
            "      label = status.value\n"
            "    after: |\n"
            "      label = status.value\n",
        )

        result = TriggerTestRunner(repo.root, RulesetLoader.local(repo.root)).run()

        assert result == RuleTestResult(
            problems=(
                ".codeguard/rule-tests/triggers/enum-usage-test.yml triggered case 1: "
                "the case changes no code in module.py",
            ),
        )

    def test_test_for_an_unknown_rule_fails(self, repo):
        repo.write(
            ".codeguard/rule-tests/triggers/enum-usage-test.yml", "id: enum-usag\ntriggered: []\n"
        )

        result = TriggerTestRunner(repo.root, RulesetLoader.local(repo.root)).run()

        assert result == RuleTestResult(
            problems=(
                ".codeguard/rule-tests/triggers/enum-usage-test.yml: no judge rule enum-usag",
            )
        )


def test_ruleset_without_trigger_tests_passes(repo):
    result = TriggerTestRunner(repo.root, RulesetLoader.local(repo.root)).run()

    assert result == RuleTestResult()
