import yaml

from codeguard.ast_grep import AstGrepTestRunner, Layout
from codeguard.rule_tests import RuleTestResult

NO_PRINT_TEST = ".codeguard/rule-tests/pattern/no-print-test.yml"
NO_PRINT_SNAPSHOT = ".codeguard/rule-tests/pattern/__snapshots__/no-print-snapshot.yml"
STALE_NO_PRINT_SNAPSHOT = (
    ".codeguard/rule-tests/pattern/__snapshots__/no-print-snapshot.yml: stale snapshot "
    "entries for no-print. Run codeguard test --update-all."
)


class TestAstGrepTestRunner:
    def test_run_without_rules_passes(self, tmp_path):
        result = AstGrepTestRunner(Layout(tmp_path)).run()

        assert result == RuleTestResult(failed=False)

    def test_run_with_passing_cases_passes(self, repo):
        repo.write(NO_PRINT_TEST, "id: no-print\nvalid:\n  - logging.info(1)\n")

        result = AstGrepTestRunner(Layout(repo.root)).run()

        assert result == RuleTestResult(failed=False)

    def test_run_with_failing_case_fails(self, repo):
        repo.write(NO_PRINT_TEST, "id: no-print\nvalid:\n  - print(1)\n")

        result = AstGrepTestRunner(Layout(repo.root)).run()

        assert result == RuleTestResult(failed=True)

    def test_run_reports_snapshot_entry_for_removed_case(self, repo):
        repo.write(NO_PRINT_TEST, "id: no-print\ninvalid:\n  - print(1)\n  - print(2)\n")
        runner = AstGrepTestRunner(Layout(repo.root))
        runner.update_snapshots()
        repo.write(NO_PRINT_TEST, "id: no-print\ninvalid:\n  - print(2)\n")

        result = runner.run()

        assert result == RuleTestResult(failed=False, problems=(STALE_NO_PRINT_SNAPSHOT,))

    def test_run_reports_snapshot_of_removed_test(self, repo):
        repo.write(NO_PRINT_TEST, "id: no-print\ninvalid:\n  - print(1)\n")
        runner = AstGrepTestRunner(Layout(repo.root))
        runner.update_snapshots()
        (repo.root / NO_PRINT_TEST).unlink()

        result = runner.run()

        assert result == RuleTestResult(failed=False, problems=(STALE_NO_PRINT_SNAPSHOT,))

    def test_update_snapshots_removes_entries_for_removed_cases(self, repo):
        repo.write(NO_PRINT_TEST, "id: no-print\ninvalid:\n  - print(1)\n  - print(2)\n")
        runner = AstGrepTestRunner(Layout(repo.root))
        runner.update_snapshots()
        repo.write(NO_PRINT_TEST, "id: no-print\ninvalid:\n  - print(2)\n")

        result = runner.update_snapshots()

        snapshot = yaml.safe_load((repo.root / NO_PRINT_SNAPSHOT).read_text())
        assert result == RuleTestResult(failed=False)
        assert list(snapshot["snapshots"]) == ["print(2)"]

    def test_update_snapshots_removes_snapshot_of_removed_test(self, repo):
        repo.write(NO_PRINT_TEST, "id: no-print\ninvalid:\n  - print(1)\n")
        runner = AstGrepTestRunner(Layout(repo.root))
        runner.update_snapshots()
        (repo.root / NO_PRINT_TEST).unlink()

        result = runner.update_snapshots()

        assert result == RuleTestResult(failed=False)
        assert not (repo.root / NO_PRINT_SNAPSHOT).exists()
