from codeguard.ast_grep import AstGrepCheck, Layout


class TestAstGrepCheck:
    def test_check_reports_violations_in_given_files_only(self, repo, make_finding):
        repo.write("checked.py", "import os\nprint(os.name)\n")
        repo.write("unchecked.py", "print(1)\n")

        findings = AstGrepCheck(Layout(repo.root)).check(["checked.py"])

        assert findings == [make_finding(file="checked.py", line=2)]

    def test_check_with_no_files_reports_nothing(self, repo):
        repo.write("unchecked.py", "print(1)\n")

        findings = AstGrepCheck(Layout(repo.root)).check([])

        assert findings == []

    def test_check_without_rules_reports_nothing(self, tmp_path):
        (tmp_path / "module.py").write_text("print(1)\n")

        findings = AstGrepCheck(Layout(tmp_path)).check(["module.py"])

        assert findings == []
