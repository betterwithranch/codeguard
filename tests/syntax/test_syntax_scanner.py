from codeguard.ast_grep import AstGrep
from codeguard.syntax import NodeKind, SyntaxNode, SyntaxScanner


class TestSyntaxScanner:
    def test_scan_finds_each_node_kind(self, tmp_path):
        (tmp_path / "order.py").write_text("import os  # system\ntotal = os.sep\n")

        [(file, parsed)] = SyntaxScanner(AstGrep()).scan(tmp_path).items()

        assert (file, parsed.content, set(parsed.nodes)) == (
            "order.py",
            b"import os  # system\ntotal = os.sep\n",
            {
                SyntaxNode(kind=NodeKind.COMMENT, start=11, end=19, text="# system"),
                SyntaxNode(kind=NodeKind.IMPORT, start=0, end=9, text="import os"),
                SyntaxNode(kind=NodeKind.NAME, start=20, end=25, text="total"),
                SyntaxNode(kind=NodeKind.NAME, start=28, end=30, text="os"),
                SyntaxNode(kind=NodeKind.NAME, start=31, end=34, text="sep"),
                SyntaxNode(kind=NodeKind.DEFINITION, start=20, end=25, text="total"),
            },
        )

    def test_scan_skips_files_in_unsupported_languages(self, tmp_path):
        (tmp_path / "order.rb").write_text("total = 1\n")

        assert SyntaxScanner(AstGrep()).scan(tmp_path) == {}
