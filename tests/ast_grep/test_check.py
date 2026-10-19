from codeguard.ast_grep import AstGrepCheck
from codeguard.config import RuleOverride, Ruleset, RulesetConfig
from codeguard.review import Severity


def packaged_ruleset(root, selection: RulesetConfig = RulesetConfig()) -> Ruleset:
    return Ruleset(name="example/python", root=root / ".codeguard", selection=selection)


class TestAstGrepCheck:
    def test_check_reports_violations_for_given_files_only(self, repo, make_diagnostic):
        repo.write("checked.py", "import os\nprint(os.name)\n")
        repo.write("unchecked.py", "print(1)\n")
        ruleset = Ruleset(name=None, root=repo.root / ".codeguard")

        diagnostics = AstGrepCheck(repo.root, ruleset).check(["checked.py"])

        assert diagnostics == [make_diagnostic(file="checked.py", line=2)]

    def test_check_with_no_files_reports_nothing(self, repo):
        repo.write("unchecked.py", "print(1)\n")
        ruleset = Ruleset(name=None, root=repo.root / ".codeguard")

        diagnostics = AstGrepCheck(repo.root, ruleset).check([])

        assert diagnostics == []

    def test_check_without_rules_reports_nothing(self, tmp_path):
        (tmp_path / "module.py").write_text("print(1)\n")
        ruleset = Ruleset(name=None, root=tmp_path / ".codeguard")

        diagnostics = AstGrepCheck(tmp_path, ruleset).check(["module.py"])

        assert diagnostics == []

    def test_packaged_rule_is_named_by_its_ruleset(self, repo, make_diagnostic):
        repo.write("a.py", "print(1)\n")

        diagnostics = AstGrepCheck(repo.root, packaged_ruleset(repo.root)).check(["a.py"])

        assert diagnostics == [make_diagnostic(rule="example/python/no-print")]

    def test_excluded_rule_reports_nothing(self, repo):
        repo.write("a.py", "print(1)\n")
        ruleset = packaged_ruleset(repo.root, RulesetConfig(exclude=("no-print",)))

        diagnostics = AstGrepCheck(repo.root, ruleset).check(["a.py"])

        assert diagnostics == []

    def test_overridden_severity_applies(self, repo, make_diagnostic):
        repo.write("a.py", "breakpoint()\n")
        selection = RulesetConfig(rules={"no-breakpoint": RuleOverride(severity="error")})

        diagnostics = AstGrepCheck(repo.root, packaged_ruleset(repo.root, selection)).check(
            ["a.py"]
        )

        assert diagnostics == [
            make_diagnostic(
                warning=True, rule="example/python/no-breakpoint", severity=Severity.ERROR
            )
        ]

    def test_ruleset_severity_sets_a_rule_without_an_override(self, repo, make_diagnostic):
        repo.write("a.py", "print(1)\n")
        selection = RulesetConfig(severity="warning")

        diagnostics = AstGrepCheck(repo.root, packaged_ruleset(repo.root, selection)).check(
            ["a.py"]
        )

        assert diagnostics == [
            make_diagnostic(rule="example/python/no-print", severity=Severity.WARNING)
        ]

    def test_rule_severity_wins_over_the_ruleset_severity(self, repo, make_diagnostic):
        repo.write("a.py", "print(1)\n")
        selection = RulesetConfig(
            severity="warning", rules={"no-print": RuleOverride(severity="error")}
        )

        diagnostics = AstGrepCheck(repo.root, packaged_ruleset(repo.root, selection)).check(
            ["a.py"]
        )

        assert diagnostics == [make_diagnostic(rule="example/python/no-print")]

    def test_overridden_paths_limit_the_rule(self, repo, make_diagnostic):
        repo.write("app/a.py", "print(1)\n")
        repo.write("scripts/b.py", "print(1)\n")
        selection = RulesetConfig(rules={"no-print": RuleOverride(paths=("app/**",))})

        diagnostics = AstGrepCheck(repo.root, packaged_ruleset(repo.root, selection)).check(
            ["app/a.py", "scripts/b.py"]
        )

        assert diagnostics == [make_diagnostic(rule="example/python/no-print", file="app/a.py")]
