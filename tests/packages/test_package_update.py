import pytest
from git_repo import GitRepo

from codeguard.packages import LockUpdate, PackageUpdate

CONFIG = ".codeguard/config.yaml"
LOCK = ".codeguard/lock.yaml"


@pytest.fixture
def remote(tmp_path_factory: pytest.TempPathFactory) -> GitRepo:
    repo = GitRepo.init(tmp_path_factory.mktemp("remote").resolve())
    for tag in ("v1.2.0", "v1.10.0", "v1.9.0", "v2.0.0", "latest"):
        repo.git("tag", tag)
    return repo


def versioned_config(remote: GitRepo) -> str:
    return (
        f"packages:\n  - git: {remote.file_url}\n    version: '>=1,<2'\n"
        "    rulesets:\n      python: {}\n"
    )


def lock_text(remote: GitRepo, ref: str) -> str:
    return f"packages:\n- git: {remote.file_url}\n  version: <2,>=1\n  ref: {ref}\n"


class TestPackageUpdate:
    def test_locks_the_newest_tag_in_the_range(self, repo, remote):
        repo.write(CONFIG, versioned_config(remote))

        updates = PackageUpdate(repo.root).run()

        assert updates == [LockUpdate(remote.file_url, None, "v1.10.0")]
        assert (repo.root / LOCK).read_text() == lock_text(remote, "v1.10.0")

    def test_moves_a_stale_lock(self, repo, remote):
        repo.write(CONFIG, versioned_config(remote))
        repo.write(LOCK, lock_text(remote, "v1.2.0"))

        updates = PackageUpdate(repo.root).run()

        assert updates == [LockUpdate(remote.file_url, "v1.2.0", "v1.10.0")]
        assert (repo.root / LOCK).read_text() == lock_text(remote, "v1.10.0")

    def test_current_lock_is_left_alone(self, repo, remote):
        repo.write(CONFIG, versioned_config(remote))
        repo.write(LOCK, lock_text(remote, "v1.10.0"))

        assert PackageUpdate(repo.root).run() == []

    def test_pinned_ref_is_left_alone(self, repo, remote):
        text = (
            f"packages:\n  - git: {remote.file_url}\n    ref: v1.2.0\n"
            "    rulesets:\n      python: {}\n"
        )
        repo.write(CONFIG, text)

        assert PackageUpdate(repo.root).run() == []
        assert (repo.root / CONFIG).read_text() == text
        assert not (repo.root / LOCK).exists()

    def test_project_without_config_has_no_updates(self, repo):
        assert PackageUpdate(repo.root).run() == []
        assert not (repo.root / LOCK).exists()


class TestLockUpdate:
    def test_names_the_package_and_both_refs(self):
        assert str(LockUpdate("https://example.com/rules.git", "v1.0.0", "v1.1.0")) == (
            "https://example.com/rules.git: v1.0.0 -> v1.1.0"
        )

    def test_names_a_first_lock_as_unlocked(self):
        assert str(LockUpdate("https://example.com/rules.git", None, "v1.1.0")) == (
            "https://example.com/rules.git: unlocked -> v1.1.0"
        )
