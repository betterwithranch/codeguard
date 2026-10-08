import json
import subprocess
import tempfile
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from codeguard.review import Concern, Finding, JudgeRequest, Verdict

CLAUDE = "claude"
JUDGE_DIRECTORY = Path(tempfile.gettempdir()) / "codeguard-judge"
VERDICT_SCHEMA = json.dumps(Verdict.model_json_schema())


@dataclass(frozen=True)
class ClaudeJudge:
    root: Path
    executable: str = CLAUDE

    def judge(self, concerns: Sequence[Concern]) -> list[Finding]:
        if not concerns:
            return []
        JUDGE_DIRECTORY.mkdir(exist_ok=True)
        with ThreadPoolExecutor(max_workers=len(concerns)) as executor:
            verdicts = list(executor.map(self._judge_concern, concerns))
        return [finding for findings in verdicts for finding in findings]

    def _judge_concern(self, concern: Concern) -> list[Finding]:
        request = JudgeRequest.from_concern(concern, self.root)
        result = subprocess.run(
            [
                self.executable,
                "--safe-mode",
                "-p",
                "--output-format", "json",
                "--json-schema", VERDICT_SCHEMA,
                "--tools", "",
                "--system-prompt", request.instructions,
                "--no-session-persistence",
            ],
            input=request.prompt,
            cwd=JUDGE_DIRECTORY,
            capture_output=True,
            text=True,
            check=True,
        )
        verdict = Verdict.model_validate(json.loads(result.stdout)["structured_output"])
        return verdict.findings_for(concern)
