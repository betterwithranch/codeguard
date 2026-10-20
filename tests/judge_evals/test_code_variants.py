from pathlib import Path

from codeguard.ast_grep import AstGrep
from codeguard.config import Skip
from codeguard.judge_evals.code_variants import CodeVariants
from codeguard.syntax import SyntaxScanner

ORDER = """\
from dataclasses import dataclass


@dataclass
class Line:
    price: int
"""

INVOICE = """\
import logging
from orders.order import Line, Order as Purchase


class Invoice:
    def __init__(self, order: Purchase, discount=0):
        self.order = order  # the order being billed
        self.discount = discount

    def total(self) -> int:
        # sum line items
        subtotal = sum(line.price for line in self.order.lines)
        logging.info(subtotal)
        return subtotal - self.discount
"""


def variant(tmp_path: Path, skip: Skip, files: dict[str, str]) -> dict[str, str]:
    for file, content in files.items():
        (tmp_path / file).write_text(content)
    variants = CodeVariants(SyntaxScanner(AstGrep()).scan(tmp_path))
    return {file: content.decode() for file, content in variants.variant(skip).items()}


class TestRenames:
    def test_renames_names_the_files_define_everywhere_they_appear(self, tmp_path):
        renamed = variant(tmp_path, Skip.RENAMES, {"order.py": ORDER, "invoice.py": INVOICE})

        assert (
            renamed["invoice.py"]
            == """\
import logging
from orders.order import name_9, Order as name_1


class name_2:
    def __init__(name_3, name_4: name_1, name_5=0):
        name_3.name_4 = name_4  # the order being billed
        name_3.name_5 = name_5

    def name_6(name_3) -> int:
        # sum line items
        name_7 = sum(name_8.name_10 for name_8 in name_3.name_4.lines)
        logging.info(name_7)
        return name_7 - name_3.name_5
"""
        )
        assert (
            renamed["order.py"]
            == """\
from dataclasses import dataclass


@dataclass
class name_9:
    name_10: int
"""
        )

    def test_keeps_builtins_modules_and_names_defined_elsewhere(self, tmp_path):
        renamed = variant(tmp_path, Skip.RENAMES, {"report.py": "print(len(orders.lines))\n"})

        assert renamed == {}

    def test_keeps_dunder_names_and_test_functions(self, tmp_path):
        source = '__all__ = ["total"]\n\n\ndef test_total():\n    total = 1\n    assert total\n'

        renamed = variant(tmp_path, Skip.RENAMES, {"test_total.py": source})

        assert renamed == {
            "test_total.py": '__all__ = ["total"]\n\n\ndef test_total():\n'
            "    name_1 = 1\n    assert name_1\n"
        }


class TestComments:
    def test_removes_comments(self, tmp_path):
        stripped = variant(tmp_path, Skip.COMMENTS, {"invoice.py": INVOICE})

        assert stripped["invoice.py"] == INVOICE.replace("# the order being billed", "").replace(
            "# sum line items", ""
        )

    def test_leaves_files_without_comments_out(self, tmp_path):
        stripped = variant(tmp_path, Skip.COMMENTS, {"order.py": ORDER})

        assert stripped == {}


class TestImports:
    def test_reverses_top_level_imports(self, tmp_path):
        reordered = variant(tmp_path, Skip.IMPORTS, {"invoice.py": INVOICE})

        assert reordered["invoice.py"].startswith(
            "from orders.order import Line, Order as Purchase\nimport logging\n"
        )

    def test_keeps_imports_inside_functions(self, tmp_path):
        source = "import os\n\n\ndef load():\n    import json\n    return json, os\n"

        reordered = variant(tmp_path, Skip.IMPORTS, {"load.py": source})

        assert reordered == {}
