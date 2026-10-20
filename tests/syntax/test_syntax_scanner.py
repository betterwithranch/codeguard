from codeguard.ast_grep import AstGrep
from codeguard.syntax import NodeKind, SyntaxNode, SyntaxScanner


class TestSyntaxScanner:
    def test_scan_finds_each_node_kind(self, tmp_path):
        (tmp_path / "order.py").write_text("import os  # system\ntotal = os.sep\n")

        [(file, parsed)] = SyntaxScanner(AstGrep()).scan(tmp_path).items()

        node_kinds = {node for node in parsed.nodes if isinstance(node.kind, NodeKind)}

        assert (file, parsed.content, node_kinds) == (
            "order.py",
            b"import os  # system\ntotal = os.sep\n",
            {
                SyntaxNode(NodeKind.COMMENT, 11, 19, "# system", start_line=1, end_line=1),
                SyntaxNode(NodeKind.IMPORT, 0, 9, "import os", start_line=1, end_line=1),
                SyntaxNode(NodeKind.NAME, 20, 25, "total", start_line=2, end_line=2),
                SyntaxNode(NodeKind.NAME, 28, 30, "os", start_line=2, end_line=2),
                SyntaxNode(NodeKind.NAME, 31, 34, "sep", start_line=2, end_line=2),
                SyntaxNode(NodeKind.DEFINITION, 20, 25, "total", start_line=2, end_line=2),
            },
        )

    def test_scope_nodes_span_their_lines(self, tmp_path):
        (tmp_path / "order.py").write_text("class Order:\n    def total(self):\n        return 1\n")

        [parsed] = SyntaxScanner(AstGrep()).scan(tmp_path).values()

        assert [(node.start_line, node.end_line) for node in parsed.of_kind(NodeKind.SCOPE)] == [
            (1, 3),
            (2, 3),
        ]

    def test_enclosing_starts_are_the_first_lines_of_scopes_around_the_lines(self, tmp_path):
        (tmp_path / "order.py").write_text(
            "class Order:\n"
            "    def total(self):\n"
            "        return 1\n"
            "\n"
            "    def name(self):\n"
            "        return 'order'\n"
            "\n"
            "x = 1\n"
        )

        [parsed] = SyntaxScanner(AstGrep()).scan(tmp_path).values()

        assert parsed.enclosing_starts([3, 8]) == frozenset({1, 2})

    def test_scan_skips_files_in_unsupported_languages(self, tmp_path):
        (tmp_path / "order.rb").write_text("total = 1\n")

        assert SyntaxScanner(AstGrep()).scan(tmp_path) == {}
