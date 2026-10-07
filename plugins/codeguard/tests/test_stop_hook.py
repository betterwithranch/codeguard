import json
from io import StringIO

from codeguard import stop_hook
from codeguard.review import Review
from codeguard.stop_event import StopEvent


class TestReviewAtStop:
    def test_reviews_uncommitted_changes(self, repo, make_finding):
        repo.write("a.py", "print(1)\n")

        result = stop_hook.review_at_stop(StopEvent(cwd=repo.root, permission_mode="default"))

        assert result == Review(findings=(make_finding(),))

    def test_plan_mode_is_skipped(self, repo):
        repo.write("a.py", "print(1)\n")

        result = stop_hook.review_at_stop(StopEvent(cwd=repo.root, permission_mode="plan"))

        assert result == Review(findings=())

    def test_merge_in_progress_is_skipped(self, repo):
        repo.git("switch", "--create", "feature")
        repo.write("a.py", "print(1)\n")
        repo.commit("Add a")
        repo.git("switch", "main")
        repo.git("merge", "--no-ff", "--no-commit", "feature")

        result = stop_hook.review_at_stop(StopEvent(cwd=repo.root, permission_mode="default"))

        assert result == Review(findings=())

    def test_removed_checkout_is_skipped(self, tmp_path):
        event = StopEvent(cwd=tmp_path / "removed", permission_mode="default")

        result = stop_hook.review_at_stop(event)

        assert result == Review(findings=())


class TestRespond:
    def test_blocking_review_writes_findings_and_returns_2(self, repo, make_finding):
        repo.write("a.py", "print(1)\n")
        stdin = StringIO(json.dumps({"cwd": str(repo.root), "permission_mode": "default"}))
        stderr = StringIO()

        code = stop_hook.respond(stdin, stderr)

        assert stderr.getvalue() == f"{make_finding()}\n"
        assert code == 2

    def test_clean_review_writes_nothing_and_returns_0(self, repo):
        repo.write("a.py", "logging.info(1)\n")
        stdin = StringIO(json.dumps({"cwd": str(repo.root), "permission_mode": "default"}))
        stderr = StringIO()

        code = stop_hook.respond(stdin, stderr)

        assert stderr.getvalue() == ""
        assert code == 0
