import subprocess

import pytest

from codeguard.gemini_provider.file_tools import FileTools


@pytest.fixture
def tools(tmp_path) -> FileTools:
    (tmp_path / "orders").mkdir()
    (tmp_path / "orders" / "order.py").write_text("class Order:\n    total = 1\n")
    (tmp_path / "orders" / "invoice.py").write_text("from orders.order import Order\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("class Hidden\n")
    return FileTools(tmp_path)


class TestFileTools:
    def test_read_file_numbers_its_lines(self, tools):
        assert tools.call("read_file", {"path": "orders/order.py"}) == (
            "     1\tclass Order:\n     2\t    total = 1\n"
        )

    def test_read_file_starts_at_the_offset(self, tools):
        assert tools.call("read_file", {"path": "orders/order.py", "offset": 2}) == (
            "     2\t    total = 1\n"
        )

    def test_read_file_outside_the_root_is_an_error(self, tools, tmp_path):
        (tmp_path.parent / "secret.txt").write_text("key\n")

        assert tools.call("read_file", {"path": "../secret.txt"}) == (
            "Error: ../secret.txt is outside the working directory"
        )

    def test_missing_file_is_an_error(self, tools):
        assert tools.call("read_file", {"path": "missing.py"}).startswith("Error: ")

    def test_grep_lists_matching_lines(self, tools):
        assert tools.call("grep", {"pattern": "^class"}) == "orders/order.py:1:class Order:"

    def test_grep_searches_only_the_glob(self, tools):
        assert tools.call("grep", {"pattern": "Order", "glob": "**/invoice.py"}) == (
            "orders/invoice.py:1:from orders.order import Order"
        )

    def test_grep_without_matches_says_so(self, tools):
        assert tools.call("grep", {"pattern": "missing"}) == "No matches."

    def test_invalid_pattern_is_an_error(self, tools):
        assert tools.call("grep", {"pattern": "("}).startswith("Error: ")

    def test_glob_lists_visible_files(self, tools):
        assert tools.call("glob", {"pattern": "**/*"}) == "orders/invoice.py\norders/order.py"

    def test_unknown_tool_is_an_error(self, tools):
        assert tools.call("write_file", {}) == "Error: there is no tool write_file."

    def test_unexpected_argument_is_an_error(self, tools):
        assert tools.call("glob", {"pattern": "*", "limit": 1}).startswith("Error: ")

    def test_grep_skips_files_git_ignores(self, tmp_path):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        (tmp_path / ".gitignore").write_text("node_modules/\n")
        (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
        (tmp_path / "node_modules" / "pkg" / "order.py").write_text("class Vendored:\n")
        (tmp_path / "order.py").write_text("class Order:\n")

        assert FileTools(tmp_path).grep("^class") == "order.py:1:class Order:"
