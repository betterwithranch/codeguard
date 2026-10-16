import pytest
from git_repo import GitRepo

from codeguard.packages import PackageUpdate

CONFIG = ".codeguard/config.yaml"


@pytest.fixture
def remote(tmp_path_factory: pytest.TempPathFactory) -> GitRepo:
    repo = GitRepo.init(tmp_path_factory.mktemp("remote").resolve())
    for tag in ("v1.2.0", "v1.10.0", "v1.9.0", "latest"):
        repo.git("tag", tag)
    return repo


class TestPackageUpdate:
    def test_moves_ref_to_the_newest_version_tag(self, repo, remote):
        repo.write(
            CONFIG,
            "# Shared rules\n"
            "packages:\n"
            f"  - git: {remote.file_url}\n"
            "    ref: v1.2.0  # pinned\n"
            "    rulesets:\n"
            "      python: {}\n",
        )

        updates = PackageUpdate(repo.root).run()

        assert [str(update) for update in updates] == [f"{remote.file_url}: v1.2.0 -> v1.10.0"]
        assert (repo.root / CONFIG).read_text() == (
            "# Shared rules\n"
            "packages:\n"
            f"  - git: {remote.file_url}\n"
            "    ref: v1.10.0  # pinned\n"
            "    rulesets:\n"
            "      python: {}\n"
        )

    def test_current_ref_is_left_alone(self, repo, remote):
        text = f"packages:\n  - git: {remote.file_url}\n    ref: v1.10.0\n    rulesets: {{}}\n"
        repo.write(CONFIG, text)

        updates = PackageUpdate(repo.root).run()

        assert updates == []
        assert (repo.root / CONFIG).read_text() == text

    def test_path_package_is_left_alone(self, repo):
        text = "packages:\n  - path: ../rules\n    rulesets: {}\n"
        repo.write(CONFIG, text)

        assert PackageUpdate(repo.root).run() == []

    def test_project_without_config_has_no_updates(self, repo):
        assert PackageUpdate(repo.root).run() == []
