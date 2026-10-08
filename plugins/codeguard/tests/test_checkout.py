from pathlib import Path

import pytest
from git_repo import GitRepo

from codeguard.checkout import Checkout


class TestCheckout:
    @pytest.fixture
    def git_repo(self, tmp_path: Path) -> GitRepo:
        return GitRepo.init(tmp_path.resolve())

    def test_containing_resolves_top_level_from_subdirectory(self, git_repo):
        git_repo.write("pkg/module.py", "")

        checkout = Checkout.containing(git_repo.root / "pkg")

        assert checkout == Checkout(root=git_repo.root)

    def test_changed_files_from_head_are_uncommitted_and_untracked_files(self, git_repo):
        git_repo.write("unstaged.py", "a = 1\n")
        git_repo.write("staged.py", "b = 1\n")
        git_repo.write("deleted.py", "c = 1\n")
        git_repo.commit("Add modules")
        git_repo.write("unstaged.py", "a = 2\n")
        git_repo.write("staged.py", "b = 2\n")
        git_repo.git("add", "staged.py")
        (git_repo.root / "deleted.py").unlink()
        git_repo.write("untracked.py", "")

        files = Checkout(root=git_repo.root).changed_files("HEAD")

        assert files == ("staged.py", "unstaged.py", "untracked.py")

    def test_changed_files_from_base_are_changes_since_merge_base(self, git_repo):
        git_repo.git("switch", "--create", "feature")
        git_repo.write("committed.py", "")
        git_repo.commit("Add committed")
        git_repo.git("switch", "main")
        git_repo.write("main_only.py", "")
        git_repo.commit("Add main_only")
        git_repo.git("switch", "feature")
        git_repo.write("untracked.py", "")

        files = Checkout(root=git_repo.root).changed_files("main")

        assert files == ("committed.py", "untracked.py")

    def test_all_files_has_tracked_and_untracked_files(self, git_repo):
        git_repo.write("tracked.py", "")
        git_repo.write("deleted.py", "")
        git_repo.commit("Add modules")
        (git_repo.root / "deleted.py").unlink()
        git_repo.write("untracked.py", "")

        files = Checkout(root=git_repo.root).all_files()

        assert files == ("tracked.py", "untracked.py")
