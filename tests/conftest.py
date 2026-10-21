from collections.abc import Iterator
from pathlib import Path

import pytest
from diskcache import Cache
from factories.diagnostic import MakeDiagnostic, MakeViolation
from factories.skill import MakeBinding, MakeSkill
from git_repo import GitRepo
from pytest_factoryboy import register

register(MakeDiagnostic)
register(MakeViolation)
register(MakeSkill)
register(MakeBinding)


@pytest.fixture(autouse=True)
def no_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LOGFIRE_TOKEN", raising=False)
    monkeypatch.setenv("LOGFIRE_IGNORE_NO_CONFIG", "1")


@pytest.fixture(autouse=True)
def committed_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEGUARD_CONFIG", raising=False)


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


@pytest.fixture
def store(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Cache]:
    with Cache(tmp_path_factory.mktemp("judgements")) as cache:
        yield cache
