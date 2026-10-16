from git_repo import GitRepo

from codeguard.working_tree import AllLines, ChangedLines, WorkingTree


class TestWorkingTree:
    def test_containing_resolves_top_level_from_subdirectory(self, tmp_path):
        git_repo = GitRepo.init(tmp_path.resolve())
        git_repo.write("pkg/module.py", "")

        working_tree = WorkingTree.containing(git_repo.root / "pkg")

        assert working_tree == WorkingTree(root=git_repo.root)

    def test_changed_files_from_head_are_uncommitted_and_untracked_files(self, tmp_path):
        git_repo = GitRepo.init(tmp_path.resolve())
        git_repo.write("unstaged.py", "a = 1\n")
        git_repo.write("staged.py", "b = 1\n")
        git_repo.write("deleted.py", "c = 1\n")
        git_repo.commit("Add modules")
        git_repo.write("unstaged.py", "a = 2\n")
        git_repo.write("staged.py", "b = 2\n")
        git_repo.git("add", "staged.py")
        (git_repo.root / "deleted.py").unlink()
        git_repo.write("untracked.py", "d = 1\n")

        changed = WorkingTree(root=git_repo.root).changed_lines("HEAD")

        assert changed.files == ("staged.py", "unstaged.py", "untracked.py")

    def test_changed_files_from_base_are_changes_since_merge_base(self, tmp_path):
        git_repo = GitRepo.init(tmp_path.resolve())
        git_repo.git("switch", "--create", "feature")
        git_repo.write("committed.py", "a = 1\n")
        git_repo.commit("Add committed")
        git_repo.git("switch", "main")
        git_repo.write("main_only.py", "b = 1\n")
        git_repo.commit("Add main_only")
        git_repo.git("switch", "feature")
        git_repo.write("untracked.py", "c = 1\n")

        changed = WorkingTree(root=git_repo.root).changed_lines("main")

        assert changed.files == ("committed.py", "untracked.py")

    def test_changed_lines_are_the_added_and_modified_lines(self, tmp_path):
        git_repo = GitRepo.init(tmp_path.resolve())
        git_repo.write("a.py", "a = 1\nb = 1\nc = 1\n")
        git_repo.commit("Add a")
        git_repo.write("a.py", "a = 1\nb = 2\nc = 1\nd = 1\n")

        changed = WorkingTree(root=git_repo.root).changed_lines("HEAD")

        assert changed == ChangedLines({"a.py": frozenset({2, 4})})

    def test_untracked_file_has_every_line_changed(self, tmp_path):
        git_repo = GitRepo.init(tmp_path.resolve())
        git_repo.write("a.py", "a = 1\nb = 1\n")

        changed = WorkingTree(root=git_repo.root).changed_lines("HEAD")

        assert changed == ChangedLines({"a.py": frozenset({1, 2})})

    def test_file_with_only_removed_lines_is_not_changed(self, tmp_path):
        git_repo = GitRepo.init(tmp_path.resolve())
        git_repo.write("a.py", "a = 1\nb = 1\n")
        git_repo.commit("Add a")
        git_repo.write("a.py", "a = 1\n")

        changed = WorkingTree(root=git_repo.root).changed_lines("HEAD")

        assert changed.files == ()

    def test_all_lines_has_tracked_and_untracked_files(self, tmp_path):
        git_repo = GitRepo.init(tmp_path.resolve())
        git_repo.write("tracked.py", "")
        git_repo.write("deleted.py", "")
        git_repo.commit("Add modules")
        (git_repo.root / "deleted.py").unlink()
        git_repo.write("untracked.py", "")

        scope = WorkingTree(root=git_repo.root).all_lines()

        assert scope == AllLines(("tracked.py", "untracked.py"))


class TestChangedLines:
    def test_covers_a_changed_line(self):
        assert ChangedLines({"a.py": frozenset({2})}).covers("a.py", 2)

    def test_does_not_cover_an_unchanged_line(self):
        assert not ChangedLines({"a.py": frozenset({2})}).covers("a.py", 1)

    def test_does_not_cover_an_unchanged_file(self):
        assert not ChangedLines({"a.py": frozenset({2})}).covers("b.py", 2)
