import pytest

from codeguard.config import RuleOverride, Ruleset, RulesetConfig
from codeguard.dead_code import DeadCodeCheck
from codeguard.review import Severity
from codeguard.working_tree import WorkingTree

NO_DEAD_CODE = "id: no-dead-code\nlanguage: python\nseverity: error\n"


@pytest.fixture
def library(repo):
    repo.write(".codeguard/rules/dead-code/no-dead-code.yml", NO_DEAD_CODE)
    repo.write("lib.py", "def helper():\n    return 1\n")
    repo.write("app.py", "from lib import helper\n\nhelper()\n")
    repo.commit("Add the library")
    return repo


class TestDeadCodeCheck:
    def test_removing_the_last_use_reports_the_definition_on_its_unchanged_line(
        self, library, make_diagnostic
    ):
        check = DeadCodeCheck(WorkingTree(library.root), local(library), library.head())
        library.write("app.py", "print(1)\n")

        assert check.check(["app.py"]) == [make_diagnostic(dead_code=True)]

    def test_removing_one_of_two_uses_reports_nothing(self, library):
        library.write("other.py", "from lib import helper\n\nhelper()\n")
        library.commit("Use the helper twice")
        check = DeadCodeCheck(WorkingTree(library.root), local(library), library.head())
        library.write("app.py", "print(1)\n")

        assert check.check(["app.py"]) == []

    def test_existing_dead_code_is_not_reported(self, library, make_diagnostic):
        library.write("lib.py", "def helper():\n    return 1\n\n\ndef old():\n    return 2\n")
        library.commit("Add dead code")
        check = DeadCodeCheck(WorkingTree(library.root), local(library), library.head())
        library.write("app.py", "print(1)\n")

        assert check.check(["app.py"]) == [make_diagnostic(dead_code=True)]

    def test_definition_the_change_adds_unused_is_not_reported(self, library):
        check = DeadCodeCheck(WorkingTree(library.root), local(library), library.head())
        library.write("new.py", "def added():\n    return 1\n")

        assert check.check(["new.py"]) == []

    def test_whitelisted_name_is_not_reported(self, library):
        library.write(
            ".codeguard/rules/dead-code/no-dead-code.yml", f"{NO_DEAD_CODE}whitelist: [help*]\n"
        )
        library.commit("Whitelist the helper")
        check = DeadCodeCheck(WorkingTree(library.root), local(library), library.head())
        library.write("app.py", "print(1)\n")

        assert check.check(["app.py"]) == []

    def test_method_the_standard_library_calls_is_not_reported(self, library):
        library.write(
            "worker.py",
            "import threading\n\n\nclass Worker(threading.Thread):\n    def run(self):\n"
            "        return 1\n\n\nWorker().run()\n",
        )
        library.commit("Add a worker")
        check = DeadCodeCheck(WorkingTree(library.root), local(library), library.head())
        library.write(
            "worker.py",
            "import threading\n\n\nclass Worker(threading.Thread):\n    def run(self):\n"
            "        return 1\n\n\nWorker().start()\n",
        )

        assert check.check(["worker.py"]) == []

    def test_excluded_rule_reports_nothing(self, library):
        ruleset = local(library, RulesetConfig(exclude=("no-dead-code",)))
        check = DeadCodeCheck(WorkingTree(library.root), ruleset, library.head())
        library.write("app.py", "print(1)\n")

        assert check.check(["app.py"]) == []

    def test_ruleset_severity_override_applies(self, library, make_diagnostic):
        selection = RulesetConfig(rules={"no-dead-code": RuleOverride(severity=Severity.WARNING)})
        check = DeadCodeCheck(WorkingTree(library.root), local(library, selection), library.head())
        library.write("app.py", "print(1)\n")

        assert check.check(["app.py"]) == [
            make_diagnostic(dead_code=True, severity=Severity.WARNING)
        ]

    def test_definition_outside_the_rule_paths_is_not_reported(self, library):
        selection = RulesetConfig(rules={"no-dead-code": RuleOverride(paths=("app/**",))})
        check = DeadCodeCheck(WorkingTree(library.root), local(library, selection), library.head())
        library.write("app.py", "print(1)\n")

        assert check.check(["app.py"]) == []

    def test_deleting_the_last_using_file_reports_the_definition(self, library, make_diagnostic):
        check = DeadCodeCheck(WorkingTree(library.root), local(library), library.head())
        (library.root / "app.py").unlink()

        assert check.check([]) == [make_diagnostic(dead_code=True)]

    def test_using_file_that_no_longer_parses_reports_nothing(self, library):
        check = DeadCodeCheck(WorkingTree(library.root), local(library), library.head())
        library.write("app.py", "from lib import helper\n\nhelper(\n")

        assert check.check(["app.py"]) == []

    def test_symlink_target_is_not_read_as_a_use(self, library):
        library.write("impl.py", "def app():\n    return 1\n")
        (library.root / "alias.py").symlink_to("app.py")
        library.commit("Alias the app")
        check = DeadCodeCheck(WorkingTree(library.root), local(library), library.head())
        library.write("lib.py", "def helper():\n    return 2\n")

        assert check.check(["lib.py"]) == []


def local(repo, selection: RulesetConfig = RulesetConfig()) -> Ruleset:
    return Ruleset(name=None, root=repo.root / ".codeguard", selection=selection)
