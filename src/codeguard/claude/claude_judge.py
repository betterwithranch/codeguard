import json
import subprocess
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path

from codeguard.review import JudgeError, JudgeRequest, Verdict

_EXECUTABLE = "claude"
_READ_ONLY_TOOLS = "Read,Grep,Glob"
_VERDICT_SCHEMA = json.dumps(Verdict.model_json_schema())


@dataclass(frozen=True)
class ClaudeJudge:
    root: Path
    model: str
    processes: AbstractContextManager[object]
    executable: str = _EXECUTABLE

    @property
    def identity(self) -> str:
        return "\0".join((_EXECUTABLE, self.model))

    def judge(self, request: JudgeRequest) -> Verdict:
        with self.processes:
            process = self._run(request)
        if process.returncode != 0:
            raise JudgeError(
                f"{self.executable} exited with {process.returncode}.\n"
                f"stdout:\n{process.stdout}\nstderr:\n{process.stderr}"
            )
        return Verdict.model_validate(json.loads(process.stdout)["structured_output"])

    def _run(self, request: JudgeRequest) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                self.executable,
                "--safe-mode",
                "-p",
                "--model",
                self.model,
                "--output-format",
                "json",
                "--json-schema",
                _VERDICT_SCHEMA,
                "--tools",
                _READ_ONLY_TOOLS,
                "--permission-prompts",
                "none",
                "--system-prompt",
                request.instructions,
                "--no-session-persistence",
            ],
            input=request.prompt,
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )
