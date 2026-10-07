from pathlib import Path

import pytest
from factories.finding import MakeFinding
from git_repo import GitRepo
from pytest_factoryboy import register

register(MakeFinding)


@pytest.fixture
def repo(tmp_path: Path) -> GitRepo:
    git_repo = GitRepo.init(tmp_path.resolve())
    git_repo.write(
        ".codeguard/rules/pattern/no-print.yml",
        "id: no-print\n"
        "language: python\n"
        "severity: error\n"
        "message: Use logging, not print.\n"
        "note: |\n"
        "  print bypasses log levels.\n"
        "  Call logger.info instead.\n"
        "rule:\n"
        "  pattern: print($$$ARGS)\n",
    )
    git_repo.write(
        ".codeguard/rules/pattern/no-breakpoint.yml",
        "id: no-breakpoint\n"
        "language: python\n"
        "severity: warning\n"
        "message: Remove breakpoint().\n"
        "rule:\n"
        "  pattern: breakpoint()\n",
    )
    git_repo.commit("Add rules")
    return git_repo
