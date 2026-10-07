import subprocess
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

    def test_changes_from_head_are_uncommitted_and_untracked_files(self, git_repo):
        git_repo.write("unstaged.py", "a = 1\n")
        git_repo.write("staged.py", "b = 1\n")
        git_repo.write("deleted.py", "c = 1\n")
        git_repo.commit("Add modules")
        git_repo.write("unstaged.py", "a = 2\n")
        git_repo.write("staged.py", "b = 2\n")
        git_repo.git("add", "staged.py")
        (git_repo.root / "deleted.py").unlink()
        git_repo.write("untracked.py", "")

        files = Checkout(root=git_repo.root).changes("HEAD")

        assert files == ("staged.py", "unstaged.py", "untracked.py")

    def test_changes_from_base_are_changes_since_merge_base(self, git_repo):
        git_repo.git("switch", "--create", "feature")
        git_repo.write("committed.py", "")
        git_repo.commit("Add committed")
        git_repo.git("switch", "main")
        git_repo.write("main_only.py", "")
        git_repo.commit("Add main_only")
        git_repo.git("switch", "feature")
        git_repo.write("untracked.py", "")

        files = Checkout(root=git_repo.root).changes("main")

        assert files == ("committed.py", "untracked.py")

    def test_all_files_has_tracked_and_untracked_files(self, git_repo):
        git_repo.write("tracked.py", "")
        git_repo.write("deleted.py", "")
        git_repo.commit("Add modules")
        (git_repo.root / "deleted.py").unlink()
        git_repo.write("untracked.py", "")

        files = Checkout(root=git_repo.root).all_files()

        assert files == ("tracked.py", "untracked.py")

    @pytest.mark.parametrize(
        ("branch", "operation"),
        [
            pytest.param("main", ("merge", "feature"), id="merge"),
            pytest.param("main", ("cherry-pick", "feature"), id="cherry-pick"),
            pytest.param("main", ("revert", "feature"), id="revert"),
            pytest.param("feature", ("rebase", "--merge", "main"), id="rebase-merge"),
            pytest.param("feature", ("rebase", "--apply", "main"), id="rebase-apply"),
        ],
    )
    def test_operation_in_progress_when_stopped_on_conflict(self, git_repo, branch, operation):
        git_repo.write("a.py", "base\n")
        git_repo.commit("Add a")
        git_repo.git("switch", "--create", "feature")
        git_repo.write("a.py", "feature\n")
        git_repo.commit("Change a on feature")
        git_repo.git("switch", "main")
        git_repo.write("a.py", "main\n")
        git_repo.commit("Change a on main")
        git_repo.git("switch", branch)
        with pytest.raises(subprocess.CalledProcessError):
            git_repo.git(*operation)

        assert Checkout(root=git_repo.root).operation_in_progress() is True

    def test_no_operation_in_progress(self, git_repo):
        assert Checkout(root=git_repo.root).operation_in_progress() is False
