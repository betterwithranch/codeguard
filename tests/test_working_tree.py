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

        assert changed == ChangedLines({"a.py": frozenset({2, 4})}, base=git_repo.head())

    def test_untracked_file_has_every_line_changed(self, tmp_path):
        git_repo = GitRepo.init(tmp_path.resolve())
        git_repo.write("a.py", "a = 1\nb = 1\n")

        changed = WorkingTree(root=git_repo.root).changed_lines("HEAD")

        assert changed == ChangedLines({"a.py": frozenset({1, 2})}, base=git_repo.head())

    def test_removed_lines_are_a_deletion_point_after_the_line_before_them(self, tmp_path):
        git_repo = GitRepo.init(tmp_path.resolve())
        git_repo.write("a.py", "a = 1\nb = 1\nc = 1\n")
        git_repo.commit("Add a")
        git_repo.write("a.py", "a = 1\nc = 1\n")

        changed = WorkingTree(root=git_repo.root).changed_lines("HEAD")

        assert changed == ChangedLines(
            lines={}, deletions={"a.py": frozenset({1})}, base=git_repo.head()
        )

    def test_base_contents_are_the_files_that_exist_in_the_base(self, tmp_path):
        git_repo = GitRepo.init(tmp_path.resolve())
        git_repo.write("a.py", "a = 1\n")
        git_repo.commit("Add a")
        git_repo.write("a.py", "a = 2\n")
        git_repo.write("new.py", "b = 1\n")

        contents = WorkingTree(root=git_repo.root).base_contents(
            git_repo.head(), ["a.py", "new.py"]
        )

        assert contents == {"a.py": b"a = 1\n"}

    def test_committed_files_are_the_files_with_the_suffix_at_the_ref(self, tmp_path):
        git_repo = GitRepo.init(tmp_path.resolve())
        git_repo.write("a.py", "a = 1\n")
        git_repo.write("pkg/b.py", "b = 1\n")
        git_repo.write("README.md", "# A\n")
        git_repo.commit("Add files")
        git_repo.write("a.py", "a = 2\n")
        git_repo.write("new.py", "c = 1\n")

        files = WorkingTree(root=git_repo.root).committed_files(git_repo.head(), ".py")

        assert files == {"a.py": b"a = 1\n", "pkg/b.py": b"b = 1\n"}

    def test_current_files_are_the_tracked_and_untracked_files_with_the_suffix(self, tmp_path):
        git_repo = GitRepo.init(tmp_path.resolve())
        git_repo.write("a.py", "a = 1\n")
        git_repo.write("deleted.py", "b = 1\n")
        git_repo.write("README.md", "# A\n")
        git_repo.commit("Add files")
        git_repo.write("a.py", "a = 2\n")
        (git_repo.root / "deleted.py").unlink()
        git_repo.write("new.py", "c = 1\n")

        files = WorkingTree(root=git_repo.root).current_files(".py")

        assert files == {"a.py": b"a = 2\n", "new.py": b"c = 1\n"}

    def test_base_contents_are_only_the_requested_files(self, tmp_path):
        git_repo = GitRepo.init(tmp_path.resolve())
        git_repo.write("pkg/a.py", "a = 1\n")
        git_repo.commit("Add pkg")

        contents = WorkingTree(root=git_repo.root).base_contents(git_repo.head(), ["pkg"])

        assert contents == {}

    def test_current_files_read_files_outside_a_sparse_checkout_from_the_index(self, tmp_path):
        git_repo = GitRepo.init(tmp_path.resolve())
        git_repo.write("a/x.py", "x = 1\n")
        git_repo.write("b/y.py", "y = 1\n")
        git_repo.commit("Add files")
        git_repo.git("sparse-checkout", "set", "a")

        files = WorkingTree(root=git_repo.root).current_files(".py")

        assert files == {"a/x.py": b"x = 1\n", "b/y.py": b"y = 1\n"}

    def test_symlinks_are_neither_committed_nor_current_files(self, tmp_path):
        git_repo = GitRepo.init(tmp_path.resolve())
        git_repo.write("a.py", "a = 1\n")
        (git_repo.root / "link.py").symlink_to("a.py")
        git_repo.commit("Add a link")
        working_tree = WorkingTree(root=git_repo.root)

        committed = working_tree.committed_files(git_repo.head(), ".py")

        assert committed == working_tree.current_files(".py") == {"a.py": b"a = 1\n"}

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

    def test_covers_the_whole_of_a_changed_file(self):
        assert ChangedLines({"a.py": frozenset({2})}).covers("a.py", None)

    def test_does_not_cover_the_whole_of_an_unchanged_file(self):
        assert not ChangedLines({"a.py": frozenset({2})}).covers("b.py", None)

    def test_covers_a_range_that_contains_a_changed_line(self):
        assert ChangedLines({"a.py": frozenset({3})}).covers("a.py", 2, end_line=4)

    def test_does_not_cover_a_range_without_a_changed_line(self):
        assert not ChangedLines({"a.py": frozenset({5})}).covers("a.py", 2, end_line=4)

    def test_covers_a_range_that_contains_a_deletion_point(self):
        changed = ChangedLines(lines={}, deletions={"a.py": frozenset({3})})

        assert changed.covers("a.py", 2, end_line=4)

    def test_covers_a_line_without_a_range_on_the_first_line_of_an_enclosing_node(self):
        changed = ChangedLines({"a.py": frozenset({3})}).with_node_starts({"a.py": frozenset({1})})

        assert changed.covers("a.py", 1)

    def test_does_not_cover_a_range_on_the_first_line_of_an_enclosing_node(self):
        changed = ChangedLines({"a.py": frozenset({5})}).with_node_starts({"a.py": frozenset({1})})

        assert not changed.covers("a.py", 1, end_line=1)
