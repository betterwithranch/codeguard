import json

from codeguard.claude import ClaudeJudge


class TestJudge:
    def test_findings_come_from_claude_structured_output(
        self, repo, tmp_path, make_concern, make_finding
    ):
        repo.write("a.py", "print(1)\n")
        output = {
            "structured_output": {
                "findings": [
                    {"file": "a.py", "line": 1, "message": "Move it.", "confidence": "low"}
                ]
            }
        }
        claude = tmp_path / "claude"
        claude.write_text(f"#!/bin/sh\ncat > /dev/null\necho '{json.dumps(output)}'\n")
        claude.chmod(0o755)

        findings = ClaudeJudge(repo.root, executable=str(claude)).judge([make_concern()])

        assert findings == [
            make_finding(
                rule="responsibility-placement",
                message="Move it.",
                note=None,
                low_confidence=True,
            )
        ]

    def test_no_concerns_runs_no_judge(self, repo, tmp_path):
        missing = tmp_path / "missing-claude"

        findings = ClaudeJudge(repo.root, executable=str(missing)).judge([])

        assert findings == []
