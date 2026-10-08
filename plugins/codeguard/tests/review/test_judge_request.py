from git_repo import GitRepo

from codeguard.review import JudgeRequest
from codeguard.review.judge_request import TEMPLATE


class TestFromConcern:
    def test_prompt_is_skill_text_then_numbered_files(self, repo, make_concern):
        repo.write("a.py", "class Order:\n    pass\n")
        repo.write("b.py", "x = 1\n")
        concern = make_concern(files=("a.py", "b.py"))

        request = JudgeRequest.from_concern(concern, repo.root)

        assert request == JudgeRequest(
            instructions=TEMPLATE,
            prompt=(
                "# Responsibility placement\n\nA method lives on the type whose data it reads.\n\n"
                '<file path="a.py">\n1\tclass Order:\n2\t    pass\n</file>\n\n'
                '<file path="b.py">\n1\tx = 1\n</file>\n'
            ),
        )

    def test_request_is_byte_identical_across_checkouts(self, tmp_path, make_concern):
        first = GitRepo(tmp_path / "first")
        second = GitRepo(tmp_path / "second")
        first.write("a.py", "print(1)\n")
        second.write("a.py", "print(1)\n")
        concern = make_concern()

        assert JudgeRequest.from_concern(concern, first.root) == JudgeRequest.from_concern(
            concern, second.root
        )
